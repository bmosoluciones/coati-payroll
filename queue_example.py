#!/usr/bin/env python
# Copyright 2025 BMO Soluciones, S.A.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Example script demonstrating the background queue system.

This script shows how to:
1. Get the queue driver
2. Register tasks
3. Enqueue tasks
4. Check task status and get feedback

Usage:
    python docs/queue_example.py
"""

from __future__ import annotations

import time
from datetime import date

from coati_payroll.queue import get_queue_driver


def example_calculation_task(value: int, multiplier: int = 2) -> dict:
    """Example task that performs a simple calculation.
    
    Args:
        value: Input value
        multiplier: Multiplier (default: 2)
        
    Returns:
        Dictionary with result
    """
    # Simulate some work
    time.sleep(1)
    
    result = value * multiplier
    return {
        "input": value,
        "multiplier": multiplier,
        "result": result,
        "timestamp": str(date.today()),
    }


def main():
    """Main demonstration function."""
    print("=" * 60)
    print("Background Queue System Example")
    print("=" * 60)
    
    # Get the queue driver (auto-selects Dramatiq or Huey)
    print("\n1. Getting queue driver...")
    queue = get_queue_driver()
    
    # Get driver info
    stats = queue.get_stats()
    print(f"   Driver: {stats.get('driver', 'unknown')}")
    print(f"   Backend: {stats.get('backend', 'unknown')}")
    print(f"   Available: {stats.get('available', False)}")
    
    # Register a task
    print("\n2. Registering example task...")
    task = queue.register_task(
        example_calculation_task,
        name="example_calc",
        max_retries=3,
    )
    print("   Task registered: example_calc")
    
    # Enqueue some tasks
    print("\n3. Enqueueing 5 tasks...")
    task_ids = []
    for i in range(1, 6):
        task_id = queue.enqueue("example_calc", value=i * 10, multiplier=3)
        task_ids.append(task_id)
        print(f"   Task {i} enqueued: value={i * 10}")
    
    # For Huey, we need to execute tasks in immediate mode for this example
    # In production, workers would process these in the background
    if hasattr(queue, 'get_huey_instance'):
        huey = queue.get_huey_instance()
        if huey:
            print("\n4. Processing tasks (Huey immediate mode for demo)...")
            # In production, you would run: huey_consumer coati_payroll.queue.drivers.huey_driver.huey
            # For this demo, we'll just show the enqueuing
            print("   Note: In production, run workers to process tasks:")
            print("   $ huey_consumer coati_payroll.queue.drivers.huey_driver.huey --workers 4")
    else:
        print("\n4. Tasks are being processed by Dramatiq workers...")
        print("   Note: Make sure Dramatiq workers are running:")
        print("   $ dramatiq coati_payroll.queue.tasks --threads 8")
    
    # Get bulk feedback
    print("\n5. Getting bulk task feedback...")
    if task_ids:
        bulk_results = queue.get_bulk_results(task_ids)
        print(f"   Total tasks: {bulk_results.get('total', 0)}")
        print(f"   Completed: {bulk_results.get('completed', 0)}")
        print(f"   Pending: {bulk_results.get('pending', 0)}")
        print(f"   Failed: {bulk_results.get('failed', 0)}")
        print(f"   Progress: {bulk_results.get('progress_percentage', 0)}%")
    
    # Show final stats
    print("\n6. Final queue statistics...")
    final_stats = queue.get_stats()
    if 'registered_tasks' in final_stats:
        print(f"   Registered tasks: {', '.join(final_stats['registered_tasks'])}")
    if 'pending_tasks' in final_stats:
        print(f"   Pending tasks: {final_stats['pending_tasks']}")
    if 'queues' in final_stats:
        print(f"   Queues: {final_stats['queues']}")
    
    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Configure Redis (for production): export REDIS_URL=redis://localhost:6379/0")
    print("2. Start workers:")
    print("   - Dramatiq: dramatiq coati_payroll.queue.tasks --threads 8")
    print("   - Huey: huey_consumer coati_payroll.queue.drivers.huey_driver.huey --workers 4")
    print("3. Use the tasks in your application to process payrolls in background")
    print("\nFor more information, see: docs/queue_system.md")


if __name__ == "__main__":
    main()
