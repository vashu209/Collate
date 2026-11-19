"""Comprehensive tests for the organizer_api FastAPI endpoints."""

from pathlib import Path
import time
import pytest
from fastapi.testclient import TestClient

from organizer.config.schema import DefaultsConfig, RuleConfig, RulesConfig
from organizer.dedup.hasher import compute_file_hash
from organizer.rules.models import FileRecord, Proposal
from organizer.storage.repository import Repository
from organizer_api.app import app
from organizer_api.dependencies import get_repo, get_rules_config


@pytest.fixture
def test_env(tmp_path: Path):
    """Provide isolated paths, repository, and FastAPI test client."""
    db_path = tmp_path / "test_api.db"
    scan_dir = tmp_path / "scandir"
    organize_dir = tmp_path / "organized"
    scan_dir.mkdir(parents=True, exist_ok=True)
    organize_dir.mkdir(parents=True, exist_ok=True)

    repo = Repository(db_path)
    repo.record_scan_root(str(scan_dir))

    rules_cfg = RulesConfig(
        version=1,
        organize_root=str(organize_dir),
        rules={
            "documents": RuleConfig(
                name="documents",
                priority=10,
                destination="Docs",
                match_any=[],
            )
        },
        defaults=DefaultsConfig(
            unmatched_category="uncategorized",
            unmatched_destination="_Uncategorized",
            min_confidence_for_proposal=0.5,
        ),
    )

    # Override dependencies
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_rules_config] = lambda: rules_cfg

    client = TestClient(app)

    yield {
        "repo": repo,
        "rules_cfg": rules_cfg,
        "scan_dir": scan_dir,
        "organize_dir": organize_dir,
        "client": client,
        "tmp_path": tmp_path,
    }

    app.dependency_overrides.clear()


def test_status_endpoint_empty(test_env):
    client = test_env["client"]
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_files_scanned"] == 0
    assert data["proposals_pending"] == 0
    assert data["latest_scan_root"] == str(test_env["scan_dir"].resolve())


def test_proposals_list_and_filters(test_env):
    repo: Repository = test_env["repo"]
    client = test_env["client"]

    # Insert file and proposals
    f1 = FileRecord(
        path=str(test_env["scan_dir"] / "paper.pdf"),
        filename="paper.pdf",
        extension="pdf",
        size_bytes=100,
        created_at=time.time(),
        modified_at=time.time(),
    )
    fid = repo.upsert_file(f1)

    p1 = Proposal(
        file_id=fid,
        source_path=f1.path,
        proposed_category="documents",
        proposed_destination=str(test_env["organize_dir"] / "Docs" / "paper.pdf"),
        confidence=0.85,
        rationale="PDF matched document rule",
        status="pending",
    )
    p2 = Proposal(
        file_id=fid,
        source_path=f1.path,
        proposed_category="images",
        proposed_destination=str(test_env["organize_dir"] / "Images" / "photo.jpg"),
        confidence=0.45,
        rationale="Low confidence test",
        status="pending",
    )
    pid1 = repo.save_proposal(p1)
    pid2 = repo.save_proposal(p2)

    # 1. Fetch all pending
    resp = client.get("/proposals")
    assert resp.status_code == 200
    items = resp.json()["proposals"]
    assert len(items) == 2
    # Sorted by confidence DESC
    assert items[0]["id"] == pid1
    assert items[1]["id"] == pid2

    # 2. Filter category
    resp_cat = client.get("/proposals?category=documents")
    assert resp_cat.status_code == 200
    cat_items = resp_cat.json()["proposals"]
    assert len(cat_items) == 1
    assert cat_items[0]["id"] == pid1

    # 3. Filter min_conf
    resp_conf = client.get("/proposals?min_conf=0.8")
    assert resp_conf.status_code == 200
    conf_items = resp_conf.json()["proposals"]
    assert len(conf_items) == 1
    assert conf_items[0]["id"] == pid1


def test_approve_proposals_execution(test_env):
    repo: Repository = test_env["repo"]
    client = test_env["client"]
    scan_dir = test_env["scan_dir"]
    organize_dir = test_env["organize_dir"]

    # Create real file in scan dir
    src_file = scan_dir / "report.pdf"
    src_file.write_text("dummy report text content")
    dest_path = organize_dir / "Docs" / "report.pdf"

    f_record = FileRecord(
        path=str(src_file),
        filename="report.pdf",
        extension="pdf",
        size_bytes=src_file.stat().st_size,
        created_at=time.time(),
        modified_at=time.time(),
        sha256=compute_file_hash(src_file),
    )
    fid = repo.upsert_file(f_record)

    proposal = Proposal(
        file_id=fid,
        source_path=str(src_file),
        proposed_category="documents",
        proposed_destination=str(dest_path),
        confidence=0.9,
        rationale="Document match",
        status="pending",
    )
    pid = repo.save_proposal(proposal)

    # Approve via endpoint
    resp = client.post("/proposals/approve", json={"ids": [pid]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["succeeded"] == 1
    assert data["failed"] == 0
    assert len(data["results"]) == 1
    res = data["results"][0]
    assert res["id"] == pid
    assert res["success"] is True
    assert res["status"] == "executed"

    # Verify filesystem changes happened safely via FileMover
    assert not src_file.exists()
    assert Path(res["destination"]).exists()

    # Verify Feedback recorded
    feedback = repo.get_feedback()
    assert len(feedback) == 1
    assert feedback[0].action == "approved"
    assert feedback[0].source_path == str(src_file)

    # Second approval attempt should fail gracefully
    resp2 = client.post("/proposals/approve", json={"ids": [pid]})
    assert resp2.status_code == 200
    assert resp2.json()["succeeded"] == 0
    assert resp2.json()["failed"] == 1


def test_reject_proposals(test_env):
    repo: Repository = test_env["repo"]
    client = test_env["client"]
    scan_dir = test_env["scan_dir"]
    organize_dir = test_env["organize_dir"]

    src_file = scan_dir / "notes.txt"
    src_file.write_text("some notes")
    dest_path = organize_dir / "Docs" / "notes.txt"

    f_record = FileRecord(
        path=str(src_file),
        filename="notes.txt",
        extension="txt",
        size_bytes=src_file.stat().st_size,
        created_at=time.time(),
        modified_at=time.time(),
    )
    fid = repo.upsert_file(f_record)

    proposal = Proposal(
        file_id=fid,
        source_path=str(src_file),
        proposed_category="documents",
        proposed_destination=str(dest_path),
        confidence=0.7,
        rationale="Text rule match",
        status="pending",
    )
    pid = repo.save_proposal(proposal)

    resp = client.post("/proposals/reject", json={"ids": [pid]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["succeeded"] == 1
    assert data["failed"] == 0
    assert data["results"][0]["status"] == "rejected"

    # Source file remains untouched
    assert src_file.exists()

    # Proposal status updated in DB
    updated = repo.get_proposal_by_id(pid)
    assert updated.status == "rejected"

    # Feedback recorded
    feedback = repo.get_feedback()
    assert len(feedback) == 1
    assert feedback[0].action == "rejected"


def test_operations_list_and_rollback(test_env):
    repo: Repository = test_env["repo"]
    client = test_env["client"]
    scan_dir = test_env["scan_dir"]
    organize_dir = test_env["organize_dir"]

    # 1. Setup file and approve move
    src_file = scan_dir / "archive.zip"
    src_file.write_text("archive contents")
    dest_path = organize_dir / "Docs" / "archive.zip"

    f_record = FileRecord(
        path=str(src_file),
        filename="archive.zip",
        extension="zip",
        size_bytes=src_file.stat().st_size,
        created_at=time.time(),
        modified_at=time.time(),
        sha256=compute_file_hash(src_file),
    )
    fid = repo.upsert_file(f_record)
    proposal = Proposal(
        file_id=fid,
        source_path=str(src_file),
        proposed_category="documents",
        proposed_destination=str(dest_path),
        confidence=0.8,
        rationale="Zip rule",
    )
    pid = repo.save_proposal(proposal)

    client.post("/proposals/approve", json={"ids": [pid]})
    assert not src_file.exists()
    assert dest_path.exists()

    # 2. Check GET /operations
    resp_ops = client.get("/operations")
    assert resp_ops.status_code == 200
    ops_data = resp_ops.json()["operations"]
    assert len(ops_data) == 1
    op_entry = ops_data[0]
    assert op_entry["has_conflict"] is False

    # 3. Rollback the operation
    op_id = op_entry["id"]
    resp_rb = client.post("/rollback", json={"operation_id": op_id})
    assert resp_rb.status_code == 200
    rb_data = resp_rb.json()
    assert rb_data["succeeded"] == 1
    assert rb_data["failed"] == 0

    # 4. Confirm source is restored and dest is removed
    assert src_file.exists()
    assert not dest_path.exists()


def test_rollback_conflict_detection(test_env):
    repo: Repository = test_env["repo"]
    client = test_env["client"]
    scan_dir = test_env["scan_dir"]
    organize_dir = test_env["organize_dir"]

    # Create moved file
    src_file = scan_dir / "contract.pdf"
    src_file.write_text("initial contract")
    dest_path = organize_dir / "Docs" / "contract.pdf"

    f_record = FileRecord(
        path=str(src_file),
        filename="contract.pdf",
        extension="pdf",
        size_bytes=src_file.stat().st_size,
        created_at=time.time(),
        modified_at=time.time(),
        sha256=compute_file_hash(src_file),
    )
    fid = repo.upsert_file(f_record)
    proposal = Proposal(
        file_id=fid,
        source_path=str(src_file),
        proposed_category="documents",
        proposed_destination=str(dest_path),
        confidence=0.88,
        rationale="Contract",
    )
    pid = repo.save_proposal(proposal)
    client.post("/proposals/approve", json={"ids": [pid]})

    # Simulate modification at destination
    dest_path.write_text("TAMPERED contract content")

    resp_ops = client.get("/operations")
    assert resp_ops.status_code == 200
    op_item = resp_ops.json()["operations"][0]
    assert op_item["has_conflict"] is True
    assert op_item["conflict_type"] == "file_modified"


def test_async_scan_and_propose_task_flow(test_env):
    client = test_env["client"]
    scan_dir = test_env["scan_dir"]

    # Create sample files
    (scan_dir / "test1.pdf").write_text("pdf document")
    (scan_dir / "test2.docx").write_text("word document")

    # 1. Trigger scan
    resp = client.post("/scan", json={"path": str(scan_dir), "recursive": False})
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    # Poll task until completion (max 5 sec)
    for _ in range(50):
        t_resp = client.get(f"/tasks/{task_id}")
        assert t_resp.status_code == 200
        if t_resp.json()["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)

    final_task = client.get(f"/tasks/{task_id}").json()
    assert final_task["status"] == "completed"
    assert final_task["result"]["files_scanned"] == 2

    # 2. Trigger propose
    p_resp = client.post("/propose", json={"model": "rules"})
    assert p_resp.status_code == 200
    p_task_id = p_resp.json()["task_id"]

    for _ in range(50):
        pt_resp = client.get(f"/tasks/{p_task_id}")
        assert pt_resp.status_code == 200
        if pt_resp.json()["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)

    final_p_task = client.get(f"/tasks/{p_task_id}").json()
    assert final_p_task["status"] == "completed"
    assert final_p_task["result"]["proposals_saved"] >= 0
