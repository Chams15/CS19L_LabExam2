"""
Operating Systems Activity
--------------------------
1. CPU Scheduling Simulation
   - FCFS                    (non-preemptive)
   - SJF                     (non-preemptive)
   - SRTF / Preemptive SJF   (preemptive)
   - Round Robin             (preemptive)
2. Banker's Algorithm (deadlock avoidance)

Outputs: Gantt Chart, Average Waiting Time, Average Turnaround Time,
         Safe State / Unsafe State and the Safe Sequence.
"""

from collections import deque


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def arrow():
    """Return a nice arrow, falling back to '->' on consoles that can't
    print unicode (e.g. some Windows terminals)."""
    try:
        "\u2192".encode(__import__("sys").stdout.encoding or "utf-8")
        return "\u2192"
    except (UnicodeEncodeError, LookupError, TypeError):
        return "->"


ARROW = arrow()


def read_int(prompt, minimum=None):
    """Read an integer from the console, re-asking until it is valid."""
    while True:
        try:
            value = int(input(prompt).strip())
            if minimum is not None and value < minimum:
                print(f"   ! Please enter a number >= {minimum}.")
                continue
            return value
        except ValueError:
            print("   ! Invalid input. Please enter a whole number.")


def read_int_list(prompt, size):
    """Read exactly `size` integers on one line (space separated)."""
    while True:
        raw = input(prompt).strip().replace(",", " ").split()
        if len(raw) != size:
            print(f"   ! Expected {size} value(s), got {len(raw)}.")
            continue
        try:
            return [int(x) for x in raw]
        except ValueError:
            print("   ! All values must be whole numbers.")


class Process:
    def __init__(self, pid, arrival, burst):
        self.pid = pid
        self.name = f"P{pid}"
        self.arrival = arrival
        self.burst = burst
        self.remaining = burst
        self.completion = 0
        self.turnaround = 0
        self.waiting = 0

    def reset(self):
        self.remaining = self.burst
        self.completion = 0
        self.turnaround = 0
        self.waiting = 0


# --------------------------------------------------------------------------
# Gantt chart + results table
# --------------------------------------------------------------------------

def draw_gantt(segments):
    """segments = list of (label, start, end)."""
    print("\nGantt Chart:")
    bar, body, ticks = "", "", ""
    for label, start, end in segments:
        width = max(len(label) + 2, len(str(start)) + 1, 4)
        bar += "+" + "-" * width
        body += "|" + label.center(width)
        ticks += str(start).ljust(width + 1)
    bar += "+"
    body += "|"
    ticks += str(segments[-1][2])

    print(bar)
    print(body)
    print(bar)
    print(ticks)


def show_results(processes):
    """Print the per-process table plus the averages."""
    processes = sorted(processes, key=lambda p: p.pid)
    print("\n" + "-" * 62)
    print(f"{'Process':<10}{'Arrival':<10}{'Burst':<10}"
          f"{'Completion':<13}{'Turnaround':<13}{'Waiting':<10}")
    print("-" * 62)
    for p in processes:
        print(f"{p.name:<10}{p.arrival:<10}{p.burst:<10}"
              f"{p.completion:<13}{p.turnaround:<13}{p.waiting:<10}")
    print("-" * 62)

    n = len(processes)
    avg_wt = sum(p.waiting for p in processes) / n
    avg_tat = sum(p.turnaround for p in processes) / n
    print(f"\nAverage Waiting Time    : {avg_wt:.2f} ms")
    print(f"Average Turnaround Time : {avg_tat:.2f} ms")


def finalize(processes):
    """Compute turnaround and waiting times once completion times are known."""
    for p in processes:
        p.turnaround = p.completion - p.arrival
        p.waiting = p.turnaround - p.burst


def add_segment(segments, label, start, end):
    """Append a slice, merging it with the previous one if it is the same
    process running back-to-back (keeps the chart readable)."""
    if segments and segments[-1][0] == label and segments[-1][2] == start:
        segments[-1] = (label, segments[-1][1], end)
    else:
        segments.append((label, start, end))


# --------------------------------------------------------------------------
# Scheduling algorithms
# --------------------------------------------------------------------------

def fcfs(processes):
    """First Come First Serve - non-preemptive."""
    order = sorted(processes, key=lambda p: (p.arrival, p.pid))
    segments, time = [], 0
    for p in order:
        if time < p.arrival:                      # CPU sits idle
            add_segment(segments, "idle", time, p.arrival)
            time = p.arrival
        add_segment(segments, p.name, time, time + p.burst)
        time += p.burst
        p.completion = time
    finalize(processes)
    return segments


def sjf_non_preemptive(processes):
    """Shortest Job First - non-preemptive."""
    segments, time, done = [], 0, 0
    n = len(processes)
    while done < n:
        ready = [p for p in processes if p.arrival <= time and p.remaining > 0]
        if not ready:
            nxt = min(p.arrival for p in processes if p.remaining > 0)
            add_segment(segments, "idle", time, nxt)
            time = nxt
            continue
        p = min(ready, key=lambda x: (x.burst, x.arrival, x.pid))
        add_segment(segments, p.name, time, time + p.remaining)
        time += p.remaining
        p.remaining = 0
        p.completion = time
        done += 1
    finalize(processes)
    return segments


def srtf(processes):
    """Shortest Remaining Time First - preemptive SJF."""
    segments, time, done = [], 0, 0
    n = len(processes)
    while done < n:
        ready = [p for p in processes if p.arrival <= time and p.remaining > 0]
        if not ready:
            nxt = min(p.arrival for p in processes if p.remaining > 0)
            add_segment(segments, "idle", time, nxt)
            time = nxt
            continue
        p = min(ready, key=lambda x: (x.remaining, x.arrival, x.pid))
        add_segment(segments, p.name, time, time + 1)   # run for 1 time unit
        p.remaining -= 1
        time += 1
        if p.remaining == 0:
            p.completion = time
            done += 1
    finalize(processes)
    return segments


def round_robin(processes, quantum):
    """Round Robin - preemptive, fixed time quantum."""
    order = sorted(processes, key=lambda p: (p.arrival, p.pid))
    segments, time, done, i = [], 0, 0, 0
    n = len(processes)
    queue = deque()

    while done < n:
        # enqueue everything that has arrived by now
        while i < n and order[i].arrival <= time:
            queue.append(order[i])
            i += 1

        if not queue:                              # CPU idle until next arrival
            add_segment(segments, "idle", time, order[i].arrival)
            time = order[i].arrival
            continue

        p = queue.popleft()
        slice_len = min(quantum, p.remaining)
        add_segment(segments, p.name, time, time + slice_len)
        time += slice_len
        p.remaining -= slice_len

        # processes that arrived DURING this slice get in line first
        while i < n and order[i].arrival <= time:
            queue.append(order[i])
            i += 1

        if p.remaining > 0:
            queue.append(p)                        # back of the queue
        else:
            p.completion = time
            done += 1

    finalize(processes)
    return segments


# --------------------------------------------------------------------------
# CPU Scheduling driver
# --------------------------------------------------------------------------

def input_processes():
    n = read_int("Enter number of processes: ", minimum=1)
    processes = []
    print()
    for i in range(n):
        arrival = read_int(f"  Arrival time of P{i}: ", minimum=0)
        burst = read_int(f"  Burst time   of P{i}: ", minimum=1)
        processes.append(Process(i, arrival, burst))
        print()
    return processes


def cpu_scheduling():
    print("\n" + "=" * 62)
    print("CPU SCHEDULING SIMULATION")
    print("=" * 62)
    processes = input_processes()

    while True:
        print("Choose a scheduling algorithm:")
        print("  [1] FCFS                      (non-preemptive)")
        print("  [2] Shortest Job First        (non-preemptive)")
        print("  [3] Shortest Remaining Time   (preemptive SJF)")
        print("  [4] Round Robin               (preemptive)")
        print("  [5] Run all four and compare")
        print("  [0] Back to main menu")
        choice = input("Choice: ").strip()

        if choice == "0":
            return

        quantum = None
        if choice in ("4", "5"):
            quantum = read_int("Enter time quantum: ", minimum=1)

        runs = []
        if choice == "1":
            runs = [("FCFS (Non-Preemptive)", fcfs, ())]
        elif choice == "2":
            runs = [("SJF (Non-Preemptive)", sjf_non_preemptive, ())]
        elif choice == "3":
            runs = [("SRTF (Preemptive SJF)", srtf, ())]
        elif choice == "4":
            runs = [(f"Round Robin (q = {quantum})", round_robin, (quantum,))]
        elif choice == "5":
            runs = [
                ("FCFS (Non-Preemptive)", fcfs, ()),
                ("SJF (Non-Preemptive)", sjf_non_preemptive, ()),
                ("SRTF (Preemptive SJF)", srtf, ()),
                (f"Round Robin (q = {quantum})", round_robin, (quantum,)),
            ]
        else:
            print("   ! Invalid choice.\n")
            continue

        for title, func, extra in runs:
            for p in processes:
                p.reset()
            print("\n" + "=" * 62)
            print(title)
            print("=" * 62)
            segments = func(processes, *extra)
            draw_gantt(segments)
            order = " ".join(
                f"{lbl}" if k == 0 else f"{ARROW} {lbl}"
                for k, (lbl, _, _) in enumerate(segments)
            )
            print(f"\nExecution Order: {order}")
            show_results(processes)
        print()


# --------------------------------------------------------------------------
# Banker's Algorithm
# --------------------------------------------------------------------------

def bankers_algorithm():
    print("\n" + "=" * 62)
    print("BANKER'S ALGORITHM (Deadlock Avoidance)")
    print("=" * 62)

    n = read_int("Enter number of processes: ", minimum=1)
    m = read_int("Enter number of resource types: ", minimum=1)

    print("\nEnter the ALLOCATION matrix (one row per process, "
          f"{m} value(s) per row):")
    allocation = [read_int_list(f"  P{i}: ", m) for i in range(n)]

    print("\nEnter the MAXIMUM matrix (one row per process, "
          f"{m} value(s) per row):")
    maximum = [read_int_list(f"  P{i}: ", m) for i in range(n)]

    print(f"\nEnter the AVAILABLE resources ({m} value(s)):")
    available = read_int_list("  Available: ", m)

    # ---- Need = Maximum - Allocation --------------------------------------
    need = [[maximum[i][j] - allocation[i][j] for j in range(m)]
            for i in range(n)]

    if any(need[i][j] < 0 for i in range(n) for j in range(m)):
        print("\n! Error: Allocation exceeds Maximum for at least one "
              "process. Please check your input.")
        return

    print("\nNeed Matrix:")
    for i in range(n):
        print(f"P{i}: {need[i]}")

    # ---- Safety algorithm --------------------------------------------------
    work = available[:]
    finish = [False] * n
    sequence = []

    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and all(need[i][j] <= work[j] for j in range(m)):
                # Pretend to grant the request, then reclaim everything.
                for j in range(m):
                    work[j] += allocation[i][j]
                finish[i] = True
                sequence.append(i)
                progress = True

    # ---- Result ------------------------------------------------------------
    if all(finish):
        print("\nSystem is in a Safe State.")
        print("Safe Sequence: " +
              f" {ARROW} ".join(f"P{i}" for i in sequence))
    else:
        unsafe = [f"P{i}" for i in range(n) if not finish[i]]
        print("\nSystem is in an UNSAFE State. Deadlock may occur.")
        print("No safe sequence exists.")
        print("Processes that cannot finish: " + ", ".join(unsafe))
    print()


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------

def main():
    while True:
        print("=" * 62)
        print("OPERATING SYSTEMS SIMULATOR")
        print("=" * 62)
        print("  [1] CPU Scheduling (FCFS / SJF / SRTF / Round Robin)")
        print("  [2] Banker's Algorithm")
        print("  [3] Exit")
        choice = input("Choice: ").strip()

        if choice == "1":
            cpu_scheduling()
        elif choice == "2":
            bankers_algorithm()
        elif choice == "3":
            print("Goodbye!")
            break
        else:
            print("   ! Invalid choice. Please pick 1, 2 or 3.\n")


if __name__ == "__main__":
    main()
