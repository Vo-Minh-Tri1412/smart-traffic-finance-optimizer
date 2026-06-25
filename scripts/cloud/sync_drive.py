from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import string
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Thư mục gốc của project
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Cấu hình các đường dẫn Local
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Tên thư mục dùng chung trên Google Drive
DRIVE_WORKSPACE_NAME = "AI Quantum HVTC — Team Workspace"

def relative_or_absolute(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def files_equal(source: Path, target: Path) -> bool:
    if not source.exists() or not target.exists():
        return False
    if source.stat().st_size != target.stat().st_size:
        return False
    return sha256_file(source) == sha256_file(target)

def candidate_drive_roots() -> list[Path]:
    candidates: list[Path] = []
    
    # Duyệt qua các ổ đĩa phổ biến
    for letter in string.ascii_uppercase:
        drive = Path(f"{letter}:/")
        candidates.extend([
            drive / "My Drive" / DRIVE_WORKSPACE_NAME,
            drive / "MyDrive" / DRIVE_WORKSPACE_NAME,
            drive / "Drive của tôi" / DRIVE_WORKSPACE_NAME,
            drive / "Shared drives" / DRIVE_WORKSPACE_NAME,
        ])
    
    # Duyệt qua thư mục Home
    home = Path.home()
    candidates.extend([
        home / "Google Drive" / "My Drive" / DRIVE_WORKSPACE_NAME,
        home / "Google Drive" / DRIVE_WORKSPACE_NAME,
        home / "My Drive" / DRIVE_WORKSPACE_NAME,
    ])
    
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        if str(path) not in seen:
            seen.add(str(path))
            unique.append(path)
    return unique

def resolve_drive_root(value: str | None) -> Path:
    if value:
        root = Path(value).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Drive root not found: {root}")
        return root

    for candidate in candidate_drive_roots():
        if candidate.exists():
            return candidate.resolve()
    
    checked = "\n".join(str(path) for path in candidate_drive_roots()[:10])
    raise FileNotFoundError(
        f"Không thể tự động tìm thấy thư mục '{DRIVE_WORKSPACE_NAME}' trên Google Drive Desktop.\n"
        f"Hãy đảm bảo bạn đã cài Google Drive Desktop và Add Shortcut thư mục này.\n"
        f"Các đường dẫn đã thử tìm:\n{checked}"
    )

def copy_tree_sync(source: Path, target: Path, *, apply: bool, description: str) -> list[dict[str, object]]:
    rows = []
    if not source.exists():
        print(f"Bỏ qua {description}: Source không tồn tại ({source})")
        return rows
        
    for src_file in source.rglob("*"):
        if not src_file.is_file():
            continue
            
        rel_path = src_file.relative_to(source)
        tgt_file = target / rel_path
        
        row = {
            "action": f"sync_{description}",
            "source": str(src_file),
            "target": str(tgt_file),
            "status": "planned"
        }
        
        if tgt_file.exists() and files_equal(src_file, tgt_file):
            row["status"] = "same"
            continue
            
        if apply:
            tgt_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, tgt_file)
            row["status"] = "copied"
        rows.append(row)
        print(f"[{row['status'].upper()}] {rel_path}")
        
    return rows

def pull_data(drive_root: Path, apply: bool) -> list[dict]:
    print("\n--- KÉO DỮ LIỆU TỪ KINH TẾ (PULL DATA) ---")
    source = drive_root / "03_Shared_Handoffs" / "From_Econ_To_CS" / "01_Final_Training_Data"
    target = DATA_DIR / "01_Final_Training_Data"
    return copy_tree_sync(source, target, apply=apply, description="pull_data")

def push_reports(drive_root: Path, apply: bool) -> list[dict]:
    print("\n--- ĐẨY BÁO CÁO CHO KINH TẾ (PUSH REPORTS) ---")
    # Lấy tên thư mục tự động theo timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    source = OUTPUTS_DIR / "final_reports"
    target = drive_root / "03_Shared_Handoffs" / "From_CS_To_Econ" / "01_Clean_Predictions" / f"Run_{timestamp}"
    
    if not source.exists() or not any(source.iterdir()):
        print(f"Không có báo cáo nào trong {source} để đẩy lên.")
        return []
        
    return copy_tree_sync(source, target, apply=apply, description="push_reports")

def push_models(drive_root: Path, apply: bool) -> list[dict]:
    print("\n--- BACKUP MODEL TRỌNG SỐ (PUSH MODELS) ---")
    source = MODELS_DIR
    target = drive_root / "02_CS_Workspace" / "03_Models_Checkpoint"
    return copy_tree_sync(source, target, apply=apply, description="push_models")

def main():
    parser = argparse.ArgumentParser(description="Công cụ đồng bộ dữ liệu với Google Drive cho Team Kỹ thuật (CS).")
    parser.add_argument("--pull-data", action="store_true", help="Kéo dữ liệu training cuối cùng từ team Kinh tế về máy.")
    parser.add_argument("--push-reports", action="store_true", help="Đẩy các file báo cáo dự đoán CSV đẹp lên Bàn Ăn cho team Kinh tế.")
    parser.add_argument("--push-models", action="store_true", help="Backup file model (.pt, .h5) lên 02_CS_Workspace.")
    parser.add_argument("--all", action="store_true", help="Chạy tất cả các luồng Push và Pull.")
    parser.add_argument("--apply", action="store_true", help="Bắt buộc phải thêm cờ này thì file mới thực sự được Copy. Nếu không, chỉ chạy nháp (Dry-run).")
    parser.add_argument("--status", action="store_true", help="Kiểm tra xem script có tìm thấy Google Drive không.")
    
    args = parser.parse_args()
    
    try:
        drive_root = resolve_drive_root(None)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
        
    if args.status:
        print(f"[OK] Đã kết nối thành công tới thư mục làm việc chung tại:\n{drive_root}")
        return

    actions = []
    
    if args.all or args.pull_data:
        actions.extend(pull_data(drive_root, args.apply))
        
    if args.all or args.push_reports:
        actions.extend(push_reports(drive_root, args.apply))
        
    if args.all or args.push_models:
        actions.extend(push_models(drive_root, args.apply))
        
    if not args.apply and any(args.__dict__.values()):
        print("\n[LƯU Ý] Đây mới chỉ là CHẠY NHÁP (Dry-run). Hãy thêm cờ --apply vào cuối lệnh để thực sự copy file.")

if __name__ == "__main__":
    main()
