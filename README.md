# Managing Data in Docker

Notes and hands-on practice for volumes, bind mounts and best practices. The demo is a tiny Python script that saves vitals readings to a CSV file. I run it with no volume, with a volume, with a bind mount and with tmpfs, and watch what happens to the data.

All data is made up.

## 1. The problem

- A container writes files into its own thin writable layer.
- That layer lives as long as the container. Stop and start it and the data is still there. Remove the container and the data is gone.
- The image never changes, so nothing a container writes goes back into it.
- To keep data, it has to be stored outside the container.

## 2. Three ways to store data outside

| | Volume | Bind mount | tmpfs |
| --- | --- | --- | --- |
| Where the data lives | A folder managed by Docker | A folder I pick on my computer | RAM only |
| Who manages it | Docker (`docker volume ...`) | Me | Docker |
| Survives `docker rm`? | Yes | Yes | No, gone when the container stops |
| Best for | Database files, app data | Code while developing, config files, files I want to open myself | Temporary or secret data |
| Example | `-v vitals-data:/data` | `-v "${PWD}/host_data:/data"` | `--tmpfs /data:mode=1777` |

Easy way to tell volume from bind mount: if the part before the colon is a plain name, it is a volume. If it is a path, it is a bind mount.

## 3. Commands

| Command | What it does |
| --- | --- |
| `docker volume create vitals-data` | Makes a volume |
| `docker volume ls` | Lists volumes |
| `docker volume inspect vitals-data` | Shows details, including where it is stored |
| `docker volume rm vitals-data` | Deletes a volume. It fails while a container uses it |
| `docker volume prune` | Deletes unused volumes. Read the list it shows before saying yes |
| `docker run -v vitals-data:/data ...` | Mounts a volume at `/data` |
| `docker run -v "${PWD}/host_data:/data" ...` | Mounts a folder from my computer |
| `docker run -v vitals-data:/data:ro ...` | Same, but read-only |
| `docker run --mount type=volume,source=vitals-data,target=/data ...` | The longer, clearer form of `-v` |
| `docker run --tmpfs /data:mode=1777 ...` | Memory-only folder that any user can write to |

`-v` and `--mount` do the same job. One difference: with a bind mount, `-v` creates the host folder if it is missing, and `--mount` gives an error instead.

## 4. The demo app

```
docker_data/
  src/
    add_reading.py             the script
  tests/
    test_add_reading.py
  Dockerfile
  .dockerignore
  .gitignore
  pytest.ini
  docker_data_practice.py      runs every step below and logs it
  README.md
```

Use it like this:

```
python src/add_reading.py P-001 120 80 72
python src/add_reading.py --show
```

- It adds one row to `readings.csv` (in the folder set by `DATA_DIR`) and prints how many readings the file now has.
- `--show` prints everything saved.
- Values outside a sensible range are refused and nothing is saved. If the folder cannot be written, it says so and exits with code 1.

The Dockerfile:

```
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /app

RUN useradd --create-home appuser \
    && mkdir /data \
    && chown appuser:appuser /data

COPY src/ ./

USER appuser

ENTRYPOINT ["python", "add_reading.py"]
```

- `DATA_DIR=/data` is the folder I mount things onto.
- The script runs as a normal user, not root. So `/data` is created in the image and given to that user. When a new empty volume is mounted there for the first time, Docker copies this folder, including its owner, into the volume. Without the `chown`, the app would get "permission denied" on the volume.
- `.dockerignore` keeps tests, `host_data` and `backups` out of the image. Data never belongs inside an image.

## 5. Hands-on practice

Easiest way: Docker Desktop running, then

```
python docker_data_practice.py
```

It runs 42 steps and saves everything to `docker_data_session.log`. Steps that must fail (writing to a read-only mount, removing a volume in use) count as worked only when they fail with the right message. It uses only its own names: image `vitals-logger`, volumes `vitals-data` and `vitals-restore`.

To do it by hand (PowerShell, in the project folder):

**Build**
```
docker build -t vitals-logger .
```

**A. No volume: the data disappears**
```
docker run --rm vitals-logger P-001 120 80 72
docker run --rm vitals-logger P-001 120 80 72
```
Both say `Readings in file: 1`. Each container starts with an empty `/data`.

```
docker run --name data-demo vitals-logger P-001 120 80 72
docker start -a data-demo
docker rm data-demo
docker run --name data-demo vitals-logger P-001 120 80 72
docker rm data-demo
```
The second command says 2, because the data survives a stop and start. After `docker rm`, the new container says 1 again.

**B. Named volume: the data stays**
```
docker volume create vitals-data
docker run --rm -v vitals-data:/data vitals-logger P-001 120 80 72
docker run --rm -v vitals-data:/data vitals-logger P-002 135 88 76
docker run --rm -v vitals-data:/data vitals-logger P-003 110 70 64
```
The count goes 1, 2, 3, even though every container is deleted after it runs.

```
docker volume ls
docker volume inspect vitals-data
docker run --rm -v vitals-data:/data alpine cat /data/readings.csv
docker run --rm --mount type=volume,source=vitals-data,target=/data vitals-logger --show
```
A different image (Alpine) can read the same volume. On Windows, the volume lives inside Docker's hidden Linux VM, so I can not browse it in File Explorer. Docker Desktop has a Volumes tab to look inside.

**C. Bind mount: a folder on my computer**
```
mkdir host_data
docker run --rm -v "${PWD}/host_data:/data" vitals-logger P-010 130 85 70
Get-Content host_data\readings.csv
```
The file is really in `host_data`. Now open `host_data\readings.csv` in VS Code, add a line at the bottom, save, and run:
```
docker run --rm -v "${PWD}/host_data:/data" vitals-logger --show
```
The container sees my edit straight away.

Read-only:
```
docker run --rm -v "${PWD}/host_data:/data:ro" vitals-logger P-012 125 82 68
docker run --rm -v "${PWD}/host_data:/data:ro" vitals-logger --show
```
Saving fails with `Read-only file system`. Showing works.

**D. tmpfs**
```
docker run --rm --tmpfs /data vitals-logger P-001 120 80 72
docker run --rm --tmpfs /data:mode=1777 vitals-logger P-001 120 80 72
```
The first one fails with `Permission denied`. A tmpfs folder is owned by root, and my script runs as a normal user. The second one adds `mode=1777`, so any user can write, and it works. Nothing is kept anywhere after the container stops.

**E. Back up and restore a volume**
```
mkdir backups
docker run --rm -v vitals-data:/data:ro -v "${PWD}/backups:/backup" alpine tar czf /backup/vitals-data.tgz -C /data .
docker volume create vitals-restore
docker run --rm -v vitals-restore:/data -v "${PWD}/backups:/backup:ro" alpine tar xzf /backup/vitals-data.tgz -C /data
docker run --rm -v vitals-restore:/data vitals-logger --show
```
A small Alpine container packs the volume into `backups\vitals-data.tgz` on my computer, then unpacks it into a brand new volume. The new volume has the same readings.

**F. Clean up**
```
docker run -d --name data-holder -v vitals-data:/data alpine sleep 300
docker volume rm vitals-data
docker rm -f data-holder
docker volume rm vitals-data vitals-restore
```
The first `volume rm` fails because a container is still using the volume. After the container is removed it works.

## 6. Best practices

- Never keep data you care about only in the container. Put it in a volume.
- Use named volumes for app data, like a database folder. Give them clear names like `vitals-data`, not the long random names Docker makes.
- Use bind mounts for development (edit code on my computer, run it in the container) and for config files. Avoid them for production data.
- Mount read-only (`:ro`) when the container only needs to read.
- Keep data and secrets out of the image. Use `.dockerignore`, mounts or environment variables.
- Run as a normal user and make sure that user owns the data folder.
- Back up volumes. A volume is not a backup, it is just storage on the same machine.
- The `VOLUME` line in a Dockerfile makes a nameless volume every time. I prefer naming the volume on `docker run`.
- Check what `docker volume prune` lists before confirming. It deletes data.
- One volume can be shared by several containers, but two programs writing the same file at the same time can break it.

## 7. Common problems

- Path with spaces on Windows: put the whole `-v "..."` value in quotes.
- `permission denied` on a bind mount (mostly Linux): the user inside the container does not match the folder's owner on the host.
- `permission denied` on a tmpfs mount: the folder is owned by root. Add `:mode=1777` to the `--tmpfs` value.
- A bind-mounted folder hides whatever the image had at that path. A volume gets the image's files copied in the first time, but only if it was empty.
- "volume is in use": a container, even a stopped one, still refers to it. Remove that container first.
- On Mac and Windows the bind mount is slower than a volume. Fine for code, bad for databases.

## 8. Tests

```
pip install pytest
python -m pytest
```

They check the CSV is created once with one header, counts go up, bad values are refused, a row added by hand is picked up, and an unusable folder gives exit code 1.

## 9. My results

*(Fill in after running.)*

- What happened to the data in Part A when the container was removed, and when it was only stopped and started?
- What count did the reading show in each of the three volume runs, and why did it keep going up?
- What did I see on my computer after the bind mount run? What happened when I edited the file?
- What happened when I mounted the folder with `:ro`?
- How did I back up and restore the volume? How many readings did the restored volume have?
- What happened when I removed a volume that was in use?

## What to submit

- The project folder (or a GitHub link).
- `docker_data_session.log`, or screenshots of the volume runs, the bind mount, the `:ro` failure and the backup.
- This README with the results filled in.

## Takeaways

- Container data is temporary. Volumes and bind mounts keep it.
- Volumes are managed by Docker and best for app data. Bind mounts point at my own folders and best for development.
- `:ro` is a cheap way to protect data from the container.
- Anything stored in a volume can be backed up with a throwaway container and `tar`.