import shutil
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_FILE = HERE / "docker_data_session.log"
HOST_DATA = HERE / "host_data"
BACKUPS = HERE / "backups"

IMAGE = "vitals-logger"
VOLUME = "vitals-data"
RESTORED = "vitals-restore"
CONTAINER = "data-demo"
HOLDER = "data-holder"

results = []


def show(command):
    return " ".join(f'"{part}"' if " " in part or "{" in part else part for part in command)


def say(text, log):
    print(text)
    log.write(text + "\n")


def part(log, title):
    say(f"\n########## {title}", log)


def record(log, ok, good, bad):
    say(good if ok else bad, log)
    results.append(ok)


def run(log, title, command, expect=None, should_fail=False, show_lines=None):
    say(f"\n=== {title}", log)
    say("$ " + show(command), log)
    try:
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, cwd=HERE)
    except FileNotFoundError:
        raise SystemExit("Docker was not found. Install Docker Desktop and reopen the terminal.")
    except subprocess.TimeoutExpired:
        record(log, False, "", "-> timed out after 10 minutes")
        return None

    output = (done.stdout + done.stderr).strip()
    lines = output.splitlines()
    if show_lines is not None and len(lines) > show_lines:
        lines = lines[:show_lines] + [f"... ({len(output.splitlines()) - show_lines} more lines)"]
    for line in lines:
        say(line, log)

    found = expect is None or expect in output
    if should_fail:
        ok = done.returncode != 0 and found
        good = f"-> failed, and that is what should happen (exit code {done.returncode})"
        bad = "-> this should have failed, but it did not" if done.returncode == 0 else f"-> failed, but not with the expected message: {expect}"
    else:
        ok = done.returncode == 0 and found
        good = "-> ok"
        bad = f"-> failed (exit code {done.returncode})" if done.returncode != 0 else f"-> ran, but the output did not contain: {expect}"
    record(log, ok, good, bad)
    return done


def mount(source, target, read_only=False):
    return f"{source}:{target}" + (":ro" if read_only else "")


def add(log, title, extra, patient, systolic, diastolic, heart_rate, expect):
    run(log, title, ["docker", "run", "--rm", *extra, IMAGE, patient, systolic, diastolic, heart_rate], expect=expect)


def main():
    with LOG_FILE.open("w", encoding="utf-8") as log:
        say(f"Docker data practice session, {datetime.now():%Y-%m-%d %H:%M:%S}", log)

        part(log, "Setup")
        run(log, "1. Docker version", ["docker", "--version"])
        run(log, "2. Is the engine running?", ["docker", "info", "--format", "server {{.ServerVersion}} on {{.OperatingSystem}}"])
        run(log, "3. Remove leftover containers from an earlier run", ["docker", "rm", "-f", CONTAINER, HOLDER])
        run(log, "4. Remove leftover volumes from an earlier run", ["docker", "volume", "rm", "-f", VOLUME, RESTORED])

        say("\n=== 5. Remove leftover folders from an earlier run", log)
        for folder in (HOST_DATA, BACKUPS):
            shutil.rmtree(folder, ignore_errors=True)
            say(f"cleared {folder}", log)
        record(log, not HOST_DATA.exists() and not BACKUPS.exists(), "-> ok", "-> failed, a folder could not be removed")

        run(log, "6. Build the image", ["docker", "build", "-t", IMAGE, "."], show_lines=6)

        part(log, "Part A: no volume. Data lives inside the container")
        add(log, "7. Save one reading", [], "P-001", "120", "80", "72", "Readings in file: 1")
        add(log, "8. Run it again. The first reading is already gone", [], "P-001", "120", "80", "72", "Readings in file: 1")
        run(log, "9. Same thing, but keep the container this time", ["docker", "run", "--name", CONTAINER, IMAGE, "P-001", "120", "80", "72"], expect="Readings in file: 1")
        run(log, "10. Start that same container again. Its data is still inside it", ["docker", "start", "-a", CONTAINER], expect="Readings in file: 2")
        run(log, "11. Remove the container", ["docker", "rm", CONTAINER])
        run(log, "12. New container with the same name. The data is gone", ["docker", "run", "--name", CONTAINER, IMAGE, "P-001", "120", "80", "72"], expect="Readings in file: 1")
        run(log, "13. Remove it again", ["docker", "rm", CONTAINER])

        part(log, "Part B: named volume. Data lives outside the container")
        run(log, "14. Create a volume", ["docker", "volume", "create", VOLUME], expect=VOLUME)
        run(log, "15. List volumes", ["docker", "volume", "ls", "--filter", f"name={VOLUME}"], expect=VOLUME)
        add(log, "16. Save a reading into the volume", ["-v", mount(VOLUME, "/data")], "P-001", "120", "80", "72", "Readings in file: 1")
        add(log, "17. Another container, same volume. The count goes up", ["-v", mount(VOLUME, "/data")], "P-002", "135", "88", "76", "Readings in file: 2")
        add(log, "18. And again", ["-v", mount(VOLUME, "/data")], "P-003", "110", "70", "64", "Readings in file: 3")
        add(log, "19. Every container above is already deleted. The data is still here", ["-v", mount(VOLUME, "/data")], "P-001", "118", "76", "70", "Readings in file: 4")
        run(log, "20. Inspect the volume", ["docker", "volume", "inspect", VOLUME, "--format", "{{.Name}} | driver {{.Driver}} | {{.Mountpoint}}"], expect=VOLUME)
        run(log, "21. A different image (Alpine) reads the same volume", ["docker", "run", "--rm", "-v", mount(VOLUME, "/data"), "alpine", "cat", "/data/readings.csv"], expect="recorded_at,patient_id,systolic,diastolic,heart_rate")
        run(log, "22. Same volume with the --mount syntax", ["docker", "run", "--rm", "--mount", f"type=volume,source={VOLUME},target=/data", IMAGE, "--show"], expect="Readings in file: 4")

        part(log, "Part C: bind mount. A folder on my own computer")
        HOST_DATA.mkdir(exist_ok=True)
        say(f"\n=== 23. Make an empty folder on my computer\n{HOST_DATA}", log)
        record(log, HOST_DATA.is_dir(), "-> ok", "-> failed, the folder was not created")
        add(log, "24. Save a reading into that folder", ["-v", mount(HOST_DATA, "/data")], "P-010", "130", "85", "70", "Readings in file: 1")

        say("\n=== 25. Look at the file from my side, without Docker", log)
        saved = HOST_DATA / "readings.csv"
        if saved.exists():
            say(saved.read_text(encoding="utf-8").strip(), log)
        record(log, saved.exists() and "P-010" in saved.read_text(encoding="utf-8"), "-> ok, the file is really on my computer", "-> failed, no readings.csv in host_data")

        say("\n=== 26. Edit the file from my side: add a reading by hand", log)
        with saved.open("a", encoding="utf-8", newline="") as handle:
            handle.write("2026-01-01T00:00:00+00:00,P-011,118,76,66\n")
        say("added P-011 to host_data/readings.csv", log)
        record(log, True, "-> ok", "")
        run(log, "27. The container sees my change straight away", ["docker", "run", "--rm", "-v", mount(HOST_DATA, "/data"), IMAGE, "--show"], expect="P-011")
        run(log, "28. Mount the folder read-only. Saving must fail", ["docker", "run", "--rm", "-v", mount(HOST_DATA, "/data", True), IMAGE, "P-012", "125", "82", "68"], expect="Read-only file system", should_fail=True)
        run(log, "29. Read-only is still fine for reading", ["docker", "run", "--rm", "-v", mount(HOST_DATA, "/data", True), IMAGE, "--show"], expect="P-011")

        part(log, "Part D: tmpfs. Memory only, nothing is kept")
        add(log, "30. Save a reading into a tmpfs mount (mode=1777 so the normal user can write)", ["--tmpfs", "/data:mode=1777"], "P-001", "120", "80", "72", "Readings in file: 1")

        part(log, "Part E: back up and restore a volume")
        BACKUPS.mkdir(exist_ok=True)
        say(f"\n=== 31. Make a folder for backups\n{BACKUPS}", log)
        record(log, BACKUPS.is_dir(), "-> ok", "-> failed, the folder was not created")
        run(log, "32. Pack the volume into a .tgz file (volume mounted read-only)", ["docker", "run", "--rm", "-v", mount(VOLUME, "/data", True), "-v", mount(BACKUPS, "/backup"), "alpine", "tar", "czf", "/backup/vitals-data.tgz", "-C", "/data", "."])

        say("\n=== 33. The backup file on my computer", log)
        archive = BACKUPS / "vitals-data.tgz"
        if archive.exists():
            say(f"{archive.name}, {archive.stat().st_size} bytes", log)
        record(log, archive.exists() and archive.stat().st_size > 0, "-> ok", "-> failed, no backup file was created")

        run(log, "34. Create a new empty volume", ["docker", "volume", "create", RESTORED], expect=RESTORED)
        run(log, "35. Unpack the backup into it", ["docker", "run", "--rm", "-v", mount(RESTORED, "/data"), "-v", mount(BACKUPS, "/backup", True), "alpine", "tar", "xzf", "/backup/vitals-data.tgz", "-C", "/data"])
        run(log, "36. The restored volume has the same 4 readings", ["docker", "run", "--rm", "-v", mount(RESTORED, "/data"), IMAGE, "--show"], expect="Readings in file: 4")

        part(log, "Part F: housekeeping")
        run(log, "37. Start a container that keeps using the volume", ["docker", "run", "-d", "--name", HOLDER, "-v", mount(VOLUME, "/data"), "alpine", "sleep", "300"])
        run(log, "38. Removing a volume that is in use must fail", ["docker", "volume", "rm", VOLUME], expect="in use", should_fail=True)
        run(log, "39. Remove that container", ["docker", "rm", "-f", HOLDER])
        run(log, "40. Now the volumes can be removed", ["docker", "volume", "rm", VOLUME, RESTORED], expect=VOLUME)
        run(log, "41. Check they are gone", ["docker", "volume", "ls", "--filter", f"name={VOLUME}"])
        run(log, "42. Disk space used by Docker", ["docker", "system", "df"])

        passed = sum(1 for ok in results if ok)
        say(f"\nDone: {passed} of {len(results)} steps worked.", log)
        say(f"The folders host_data and backups are still here, so you can look at the files. Delete them when you are done.", log)
        say(f"Full output saved in {LOG_FILE}", log)


if __name__ == "__main__":
    main()