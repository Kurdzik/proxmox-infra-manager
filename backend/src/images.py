"""Curated registry of common VM ISO images with download URLs."""

COMMON_IMAGES: list[dict] = [
    {
        "id": "ubuntu-2404",
        "name": "Ubuntu 24.04 LTS",
        "description": "Noble Numbat — LTS until 2029",
        "os_family": "ubuntu",
        "filename": "ubuntu-24.04.1-live-server-amd64.iso",
        "url": "https://releases.ubuntu.com/24.04/ubuntu-24.04.1-live-server-amd64.iso",
        "size_gb": 2.7,
    },
    {
        "id": "ubuntu-2204",
        "name": "Ubuntu 22.04 LTS",
        "description": "Jammy Jellyfish — LTS until 2027",
        "os_family": "ubuntu",
        "filename": "ubuntu-22.04.4-live-server-amd64.iso",
        "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04.4-live-server-amd64.iso",
        "size_gb": 2.1,
    },
    {
        "id": "ubuntu-2004",
        "name": "Ubuntu 20.04 LTS",
        "description": "Focal Fossa — LTS until 2025",
        "os_family": "ubuntu",
        "filename": "ubuntu-20.04.6-live-server-amd64.iso",
        "url": "https://releases.ubuntu.com/20.04/ubuntu-20.04.6-live-server-amd64.iso",
        "size_gb": 1.4,
    },
    {
        "id": "debian-12",
        "name": "Debian 12 Bookworm",
        "description": "Stable — minimal netinstall",
        "os_family": "debian",
        "filename": "debian-12.5.0-amd64-netinst.iso",
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.5.0-amd64-netinst.iso",
        "size_gb": 0.7,
    },
    {
        "id": "debian-11",
        "name": "Debian 11 Bullseye",
        "description": "Oldstable — minimal netinstall",
        "os_family": "debian",
        "filename": "debian-11.9.0-amd64-netinst.iso",
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-11.9.0-amd64-netinst.iso",
        "size_gb": 0.4,
    },
    {
        "id": "rocky-9",
        "name": "Rocky Linux 9",
        "description": "RHEL-compatible — production-grade",
        "os_family": "rhel",
        "filename": "Rocky-9.4-x86_64-minimal.iso",
        "url": "https://download.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9.4-x86_64-minimal.iso",
        "size_gb": 1.8,
    },
    {
        "id": "almalinux-9",
        "name": "AlmaLinux 9",
        "description": "RHEL-compatible enterprise Linux",
        "os_family": "rhel",
        "filename": "AlmaLinux-9.4-x86_64-minimal.iso",
        "url": "https://repo.almalinux.org/almalinux/9.4/isos/x86_64/AlmaLinux-9.4-x86_64-minimal.iso",
        "size_gb": 1.8,
    },
    {
        "id": "alpine-320",
        "name": "Alpine Linux 3.20",
        "description": "Minimal, security-focused",
        "os_family": "alpine",
        "filename": "alpine-standard-3.20.1-x86_64.iso",
        "url": "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/alpine-standard-3.20.1-x86_64.iso",
        "size_gb": 0.2,
    },
]

# Fast lookup: filename -> image record
IMAGE_BY_FILENAME: dict[str, dict] = {img["filename"]: img for img in COMMON_IMAGES}
IMAGE_BY_ID: dict[str, dict] = {img["id"]: img for img in COMMON_IMAGES}


def storage_path(storage: str, filename: str) -> str:
    """Build the Proxmox storage path, e.g. local:iso/ubuntu-24.04.iso"""
    return f"{storage}:iso/{filename}"


def parse_storage_path(os_image: str) -> tuple[str, str] | None:
    """
    Parse 'local:iso/ubuntu-24.04.iso' → ('local', 'ubuntu-24.04.iso').
    Returns None if the path doesn't follow the expected format.
    """
    try:
        storage, rest = os_image.split(":", 1)
        filename = rest.split("/")[-1]
        return storage, filename
    except Exception:
        return None
