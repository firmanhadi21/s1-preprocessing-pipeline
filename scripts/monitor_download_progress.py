#!/usr/bin/env python3
"""
Monitor download progress in real-time

Watches download_status.json and provides live updates
"""

import json
import time
from pathlib import Path
from datetime import timedelta
import sys

def format_size(bytes):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"

def monitor(status_file='workspace/downloads/download_status.json', interval=5):
    """Monitor download progress"""

    status_path = Path(status_file)

    if not status_path.exists():
        print(f"Status file not found: {status_file}")
        print("Download may not have started yet")
        return

    print("="*70)
    print("DOWNLOAD PROGRESS MONITOR")
    print("="*70)
    print(f"Monitoring: {status_file}")
    print(f"Update interval: {interval} seconds")
    print(f"Press Ctrl+C to stop\n")

    last_size = 0
    last_time = time.time()

    try:
        while True:
            with open(status_path, 'r') as f:
                status = json.load(f)

            # Calculate statistics
            total = len(status)
            completed = sum(1 for v in status.values() if v['status'] == 'completed')
            failed = sum(1 for v in status.values() if v['status'] == 'failed')
            in_progress = total - completed - failed

            # Calculate total size
            total_size_mb = sum(
                v.get('size_mb', 0) for v in status.values()
                if v['status'] == 'completed'
            )
            total_size_gb = total_size_mb / 1024

            # Calculate download rate
            current_time = time.time()
            elapsed = current_time - last_time

            if elapsed > 0 and total_size_mb > last_size:
                rate_mbps = (total_size_mb - last_size) / elapsed
                last_size = total_size_mb
                last_time = current_time
            else:
                rate_mbps = 0

            # Progress percentage
            if total > 0:
                percent = (completed / total) * 100
                bar_length = 50
                filled = int(bar_length * completed / total)
                bar = "█" * filled + "░" * (bar_length - filled)
            else:
                percent = 0
                bar = "░" * 50

            # Display
            print(f"\r{bar} {percent:.1f}%", end='')
            print(f" | ✓ {completed}/{total}", end='')
            print(f" | ✗ {failed}", end='')
            print(f" | {total_size_gb:.1f} GB", end='')
            if rate_mbps > 0:
                print(f" | {rate_mbps:.1f} MB/s", end='')
            print("  ", end='', flush=True)

            # Check if complete
            if completed + failed == total and total > 0:
                print("\n\n✓ Download complete!")
                print(f"Total: {completed}/{total} scenes")
                print(f"Failed: {failed}")
                print(f"Size: {total_size_gb:.1f} GB")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")
        print(f"Final status: {completed}/{total} completed, {failed} failed")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Monitor download progress')
    parser.add_argument('--status-file', default='workspace/downloads/download_status.json',
                       help='Path to download_status.json')
    parser.add_argument('--interval', type=int, default=5,
                       help='Update interval in seconds (default: 5)')

    args = parser.parse_args()

    monitor(args.status_file, args.interval)
