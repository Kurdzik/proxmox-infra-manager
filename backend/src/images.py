"""Curated registry of common VM images with download URLs.

image_type:
  "iso"          — traditional installer ISO; user installs OS manually.
  "cloud-image"  — pre-built cloud image; provisioned with cloud-init, ready on first boot.
                   Includes qemu-guest-agent so IPs are visible immediately after boot.
"""

COMMON_IMAGES: list[dict] = [
    # ── Cloud images (recommended) ─────────────────────────────────────────
    {
        "id": "ubuntu-2404-cloud",
        "name": "Ubuntu 24.04 LTS Cloud",
        "description": "Noble Numbat cloud image — boots in seconds, IP auto-assigned via DHCP",
        "os_family": "ubuntu",
        "image_type": "cloud-image",
        "filename": "ubuntu-24.04-server-cloudimg-amd64.img",
        "url": "https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img",
        "size_gb": 0.6,
    },
    {
        "id": "ubuntu-2204-cloud",
        "name": "Ubuntu 22.04 LTS Cloud",
        "description": "Jammy Jellyfish cloud image — boots in seconds, IP auto-assigned via DHCP",
        "os_family": "ubuntu",
        "image_type": "cloud-image",
        "filename": "ubuntu-22.04-server-cloudimg-amd64.img",
        "url": "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-amd64.img",
        "size_gb": 0.6,
    },
    {
        "id": "debian-12-cloud",
        "name": "Debian 12 Cloud",
        "description": "Bookworm cloud image — boots in seconds, IP auto-assigned via DHCP",
        "os_family": "debian",
        "image_type": "cloud-image",
        # Debian's generic cloud image saved with .img extension so Proxmox download-url accepts it
        "filename": "debian-12-genericcloud-amd64.img",
        "url": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2",
        "size_gb": 0.4,
    },
    {
        "id": "debian-11-cloud",
        "name": "Debian 11 Cloud",
        "description": "Bullseye cloud image — stable, boots in seconds",
        "os_family": "debian",
        "image_type": "cloud-image",
        "filename": "debian-11-genericcloud-amd64.img",
        "url": "https://cloud.debian.org/images/cloud/bullseye/latest/debian-11-genericcloud-amd64.qcow2",
        "size_gb": 0.3,
    },
    {
        "id": "ubuntu-2004-cloud",
        "name": "Ubuntu 20.04 LTS Cloud",
        "description": "Focal Fossa cloud image — LTS until 2025",
        "os_family": "ubuntu",
        "image_type": "cloud-image",
        "filename": "ubuntu-20.04-server-cloudimg-amd64.img",
        "url": "https://cloud-images.ubuntu.com/releases/20.04/release/ubuntu-20.04-server-cloudimg-amd64.img",
        "size_gb": 0.5,
    },
    {
        "id": "rocky-9-cloud",
        "name": "Rocky Linux 9 Cloud",
        "description": "RHEL-compatible cloud image — production-grade",
        "os_family": "rhel",
        "image_type": "cloud-image",
        "filename": "Rocky-9-GenericCloud.latest.x86_64.img",
        "url": "https://dl.rockylinux.org/pub/rocky/9/images/x86_64/Rocky-9-GenericCloud.latest.x86_64.qcow2",
        "size_gb": 0.7,
    },
    {
        "id": "almalinux-9-cloud",
        "name": "AlmaLinux 9 Cloud",
        "description": "RHEL-compatible enterprise cloud image",
        "os_family": "rhel",
        "image_type": "cloud-image",
        "filename": "AlmaLinux-9-GenericCloud.latest.x86_64.img",
        "url": "https://repo.almalinux.org/almalinux/9/cloud/x86_64/images/AlmaLinux-9-GenericCloud.latest.x86_64.qcow2",
        "size_gb": 0.7,
    },
    {
        "id": "fedora-40-cloud",
        "name": "Fedora 40 Cloud",
        "description": "Cutting-edge Fedora cloud image",
        "os_family": "rhel",
        "image_type": "cloud-image",
        "filename": "Fedora-Cloud-Base-Generic.x86_64-40-1.14.img",
        "url": "https://download.fedoraproject.org/pub/fedora/linux/releases/40/Cloud/x86_64/images/Fedora-Cloud-Base-Generic.x86_64-40-1.14.qcow2",
        "size_gb": 0.3,
    },
    # ── ISO installers ─────────────────────────────────────────────────────
    {
        "id": "ubuntu-2404",
        "name": "Ubuntu 24.04 LTS",
        "description": "Noble Numbat — LTS until 2029",
        "os_family": "ubuntu",
        "image_type": "iso",
        "filename": "ubuntu-24.04.1-live-server-amd64.iso",
        "url": "https://releases.ubuntu.com/24.04/ubuntu-24.04.1-live-server-amd64.iso",
        "size_gb": 2.7,
    },
    {
        "id": "ubuntu-2204",
        "name": "Ubuntu 22.04 LTS",
        "description": "Jammy Jellyfish — LTS until 2027",
        "os_family": "ubuntu",
        "image_type": "iso",
        "filename": "ubuntu-22.04.4-live-server-amd64.iso",
        "url": "https://releases.ubuntu.com/22.04/ubuntu-22.04.4-live-server-amd64.iso",
        "size_gb": 2.1,
    },
    {
        "id": "ubuntu-2004",
        "name": "Ubuntu 20.04 LTS",
        "description": "Focal Fossa — LTS until 2025",
        "os_family": "ubuntu",
        "image_type": "iso",
        "filename": "ubuntu-20.04.6-live-server-amd64.iso",
        "url": "https://releases.ubuntu.com/20.04/ubuntu-20.04.6-live-server-amd64.iso",
        "size_gb": 1.4,
    },
    {
        "id": "debian-12",
        "name": "Debian 12 Bookworm",
        "description": "Stable — minimal netinstall",
        "os_family": "debian",
        "image_type": "iso",
        "filename": "debian-12.5.0-amd64-netinst.iso",
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.5.0-amd64-netinst.iso",
        "size_gb": 0.7,
    },
    {
        "id": "debian-11",
        "name": "Debian 11 Bullseye",
        "description": "Oldstable — minimal netinstall",
        "os_family": "debian",
        "image_type": "iso",
        "filename": "debian-11.9.0-amd64-netinst.iso",
        "url": "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-11.9.0-amd64-netinst.iso",
        "size_gb": 0.4,
    },
    {
        "id": "rocky-9",
        "name": "Rocky Linux 9",
        "description": "RHEL-compatible — production-grade",
        "os_family": "rhel",
        "image_type": "iso",
        "filename": "Rocky-9.4-x86_64-minimal.iso",
        "url": "https://download.rockylinux.org/pub/rocky/9/isos/x86_64/Rocky-9.4-x86_64-minimal.iso",
        "size_gb": 1.8,
    },
    {
        "id": "almalinux-9",
        "name": "AlmaLinux 9",
        "description": "RHEL-compatible enterprise Linux",
        "os_family": "rhel",
        "image_type": "iso",
        "filename": "AlmaLinux-9.4-x86_64-minimal.iso",
        "url": "https://repo.almalinux.org/almalinux/9.4/isos/x86_64/AlmaLinux-9.4-x86_64-minimal.iso",
        "size_gb": 1.8,
    },
    {
        "id": "alpine-320",
        "name": "Alpine Linux 3.20",
        "description": "Minimal, security-focused",
        "os_family": "alpine",
        "image_type": "iso",
        "filename": "alpine-standard-3.20.1-x86_64.iso",
        "url": "https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/alpine-standard-3.20.1-x86_64.iso",
        "size_gb": 0.2,
    },
]

# Fast lookup: filename -> image record
IMAGE_BY_FILENAME: dict[str, dict] = {img["filename"]: img for img in COMMON_IMAGES}
IMAGE_BY_ID: dict[str, dict] = {img["id"]: img for img in COMMON_IMAGES}


def is_cloud_image(image_id: str) -> bool:
    img = IMAGE_BY_ID.get(image_id)
    return img is not None and img.get("image_type") == "cloud-image"


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
