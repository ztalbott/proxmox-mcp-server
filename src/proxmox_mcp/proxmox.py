"""Thin wrapper around proxmoxer — clean Python methods for every API call."""
from __future__ import annotations
import urllib3
from typing import Any

try:
    from proxmoxer import ProxmoxAPI as _ProxmoxAPI
    HAS_PROXMOXER = True
except ImportError:
    HAS_PROXMOXER = False


class ProxmoxClient:
    def __init__(self, host: str, token_id: str, token_secret: str, verify_ssl: bool = True):
        if not HAS_PROXMOXER:
            raise RuntimeError("proxmoxer is not installed. Run: pip install proxmoxer requests")
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if "!" not in token_id:
            raise ValueError(f"PROXMOX_TOKEN_ID must be 'user@realm!tokenname', got: {token_id!r}")
        user, token_name = token_id.rsplit("!", 1)
        self.pve = _ProxmoxAPI(
            host, user=user, token_name=token_name,
            token_value=token_secret, verify_ssl=verify_ssl
        )

    # ── Cluster / Nodes ────────────────────────────────────────────────────────

    def list_nodes(self) -> list[dict]:
        return self.pve.nodes.get()

    def get_node_status(self, node: str) -> dict:
        return self.pve.nodes(node).status.get()

    def reboot_node(self, node: str) -> str:
        return self.pve.nodes(node).status.post(command="reboot")

    def shutdown_node(self, node: str) -> str:
        return self.pve.nodes(node).status.post(command="shutdown")

    def list_cluster_resources(self, resource_type: str | None = None) -> list[dict]:
        kwargs: dict[str, Any] = {}
        if resource_type:
            kwargs["type"] = resource_type
        return self.pve.cluster.resources.get(**kwargs)

    def get_cluster_status(self) -> list[dict]:
        return self.pve.cluster.status.get()

    def list_storage(self, node: str | None = None) -> list[dict]:
        return self.pve.nodes(node).storage.get() if node else self.pve.storage.get()

    def list_storage_content(self, node: str, storage: str, content_type: str | None = None) -> list[dict]:
        kwargs: dict[str, Any] = {}
        if content_type:
            kwargs["content"] = content_type
        return self.pve.nodes(node).storage(storage).content.get(**kwargs)

    def delete_storage_content(self, node: str, storage: str, volume: str) -> str:
        return self.pve.nodes(node).storage(storage).content(volume).delete()

    def list_networks(self, node: str) -> list[dict]:
        return self.pve.nodes(node).network.get()

    def list_tasks(self, node: str, limit: int = 50) -> list[dict]:
        return self.pve.nodes(node).tasks.get(limit=limit)

    def get_task_status(self, node: str, upid: str) -> dict:
        return self.pve.nodes(node).tasks(upid).status.get()

    def get_task_log(self, node: str, upid: str) -> list[dict]:
        return self.pve.nodes(node).tasks(upid).log.get()

    def list_pools(self) -> list[dict]:
        return self.pve.pools.get()

    def get_pool(self, poolid: str) -> dict:
        return self.pve.pools(poolid).get()

    def create_pool(self, poolid: str, comment: str = "") -> str:
        kwargs: dict[str, Any] = {"poolid": poolid}
        if comment:
            kwargs["comment"] = comment
        return self.pve.pools.post(**kwargs)

    def delete_pool(self, poolid: str) -> str:
        return self.pve.pools(poolid).delete()

    def list_users(self) -> list[dict]:
        return self.pve.access.users.get()

    def get_version(self) -> dict:
        return self.pve.version.get()

    # ── VMs ────────────────────────────────────────────────────────────────────

    def list_vms(self, node: str | None = None) -> list[dict]:
        return self.pve.nodes(node).qemu.get() if node else self.list_cluster_resources("vm")

    def get_vm_status(self, node: str, vmid: int) -> dict:
        return self.pve.nodes(node).qemu(vmid).status.current.get()

    def get_vm_config(self, node: str, vmid: int) -> dict:
        return self.pve.nodes(node).qemu(vmid).config.get()

    def start_vm(self, node: str, vmid: int) -> str:
        return self.pve.nodes(node).qemu(vmid).status.start.post()

    def stop_vm(self, node: str, vmid: int, force: bool = False) -> str:
        if force:
            return self.pve.nodes(node).qemu(vmid).status.stop.post()
        return self.pve.nodes(node).qemu(vmid).status.shutdown.post()

    def reboot_vm(self, node: str, vmid: int) -> str:
        return self.pve.nodes(node).qemu(vmid).status.reboot.post()

    def suspend_vm(self, node: str, vmid: int) -> str:
        return self.pve.nodes(node).qemu(vmid).status.suspend.post()

    def resume_vm(self, node: str, vmid: int) -> str:
        return self.pve.nodes(node).qemu(vmid).status.resume.post()

    def set_vm_config(self, node: str, vmid: int, **config: Any) -> str:
        return self.pve.nodes(node).qemu(vmid).config.put(**config)

    def create_vm(self, node: str, vmid: int, name: str,
                  cores: int = 1, memory: int = 512, **kwargs: Any) -> str:
        return self.pve.nodes(node).qemu.post(
            vmid=vmid, name=name, cores=cores, memory=memory, **kwargs
        )

    def clone_vm(self, node: str, vmid: int, newid: int,
                 name: str | None = None, full: bool = True,
                 target_node: str | None = None) -> str:
        kwargs: dict[str, Any] = {"newid": newid, "full": 1 if full else 0}
        if name:
            kwargs["name"] = name
        if target_node:
            kwargs["target"] = target_node
        return self.pve.nodes(node).qemu(vmid).clone.post(**kwargs)

    def migrate_vm(self, node: str, vmid: int, target_node: str,
                   online: bool = True) -> str:
        return self.pve.nodes(node).qemu(vmid).migrate.post(
            target=target_node, online=1 if online else 0
        )

    def destroy_vm(self, node: str, vmid: int, purge: bool = True) -> str:
        return self.pve.nodes(node).qemu(vmid).delete(
            purge=1 if purge else 0, **{"destroy-unreferenced-disks": 1}
        )

    def resize_vm_disk(self, node: str, vmid: int, disk: str, size: str) -> str:
        """size: e.g. '+10G' to grow by 10 GB, or '50G' for absolute."""
        return self.pve.nodes(node).qemu(vmid).resize.put(disk=disk, size=size)

    def list_vm_snapshots(self, node: str, vmid: int) -> list[dict]:
        return self.pve.nodes(node).qemu(vmid).snapshot.get()

    def snapshot_vm(self, node: str, vmid: int, snapname: str,
                    description: str | None = None, vmstate: bool = False) -> str:
        kwargs: dict[str, Any] = {"snapname": snapname, "vmstate": 1 if vmstate else 0}
        if description:
            kwargs["description"] = description
        return self.pve.nodes(node).qemu(vmid).snapshot.post(**kwargs)

    def rollback_vm_snapshot(self, node: str, vmid: int, snapname: str) -> str:
        return self.pve.nodes(node).qemu(vmid).snapshot(snapname).rollback.post()

    def delete_vm_snapshot(self, node: str, vmid: int, snapname: str) -> str:
        return self.pve.nodes(node).qemu(vmid).snapshot(snapname).delete()

    def list_vm_backups(self, node: str, storage: str) -> list[dict]:
        return self.list_storage_content(node, storage, content_type="backup")

    def backup_vm(self, node: str, vmid: int, storage: str,
                  mode: str = "snapshot", compress: str = "zstd") -> str:
        return self.pve.nodes(node).vzdump.post(
            vmid=vmid, storage=storage, mode=mode, compress=compress
        )

    # ── LXC ────────────────────────────────────────────────────────────────────

    def list_lxc(self, node: str | None = None) -> list[dict]:
        return self.pve.nodes(node).lxc.get() if node else self.list_cluster_resources("lxc")

    def get_lxc_status(self, node: str, vmid: int) -> dict:
        return self.pve.nodes(node).lxc(vmid).status.current.get()

    def get_lxc_config(self, node: str, vmid: int) -> dict:
        return self.pve.nodes(node).lxc(vmid).config.get()

    def start_lxc(self, node: str, vmid: int) -> str:
        return self.pve.nodes(node).lxc(vmid).status.start.post()

    def stop_lxc(self, node: str, vmid: int, force: bool = False) -> str:
        if force:
            return self.pve.nodes(node).lxc(vmid).status.stop.post()
        return self.pve.nodes(node).lxc(vmid).status.shutdown.post()

    def reboot_lxc(self, node: str, vmid: int) -> str:
        return self.pve.nodes(node).lxc(vmid).status.reboot.post()

    def set_lxc_config(self, node: str, vmid: int, **config: Any) -> str:
        return self.pve.nodes(node).lxc(vmid).config.put(**config)

    def create_lxc(self, node: str, vmid: int, ostemplate: str,
                   hostname: str | None = None, cores: int = 1,
                   memory: int = 512, **kwargs: Any) -> str:
        params: dict[str, Any] = {
            "vmid": vmid, "ostemplate": ostemplate,
            "cores": cores, "memory": memory
        }
        if hostname:
            params["hostname"] = hostname
        params.update(kwargs)
        return self.pve.nodes(node).lxc.post(**params)

    def clone_lxc(self, node: str, vmid: int, newid: int,
                  hostname: str | None = None, full: bool = True) -> str:
        kwargs: dict[str, Any] = {"newid": newid, "full": 1 if full else 0}
        if hostname:
            kwargs["hostname"] = hostname
        return self.pve.nodes(node).lxc(vmid).clone.post(**kwargs)

    def migrate_lxc(self, node: str, vmid: int, target_node: str,
                    restart: bool = True) -> str:
        return self.pve.nodes(node).lxc(vmid).migrate.post(
            target=target_node, restart=1 if restart else 0
        )

    def destroy_lxc(self, node: str, vmid: int) -> str:
        return self.pve.nodes(node).lxc(vmid).delete()

    def resize_lxc_disk(self, node: str, vmid: int, disk: str, size: str) -> str:
        return self.pve.nodes(node).lxc(vmid).resize.put(disk=disk, size=size)

    def list_lxc_snapshots(self, node: str, vmid: int) -> list[dict]:
        return self.pve.nodes(node).lxc(vmid).snapshot.get()

    def snapshot_lxc(self, node: str, vmid: int, snapname: str,
                     description: str | None = None) -> str:
        kwargs: dict[str, Any] = {"snapname": snapname}
        if description:
            kwargs["description"] = description
        return self.pve.nodes(node).lxc(vmid).snapshot.post(**kwargs)

    def rollback_lxc_snapshot(self, node: str, vmid: int, snapname: str) -> str:
        return self.pve.nodes(node).lxc(vmid).snapshot(snapname).rollback.post()

    def delete_lxc_snapshot(self, node: str, vmid: int, snapname: str) -> str:
        return self.pve.nodes(node).lxc(vmid).snapshot(snapname).delete()

    def backup_lxc(self, node: str, vmid: int, storage: str,
                   mode: str = "snapshot", compress: str = "zstd") -> str:
        return self.pve.nodes(node).vzdump.post(
            vmid=vmid, storage=storage, mode=mode, compress=compress
        )

    # ── Firewall ───────────────────────────────────────────────────────────────

    def _fw(self, scope: str, node: str | None, vmid: int | None):
        if scope == "datacenter":
            return self.pve.cluster.firewall
        if scope == "node" and node:
            return self.pve.nodes(node).firewall
        if scope == "vm" and node and vmid:
            return self.pve.nodes(node).qemu(vmid).firewall
        if scope == "lxc" and node and vmid:
            return self.pve.nodes(node).lxc(vmid).firewall
        raise ValueError(f"Invalid scope={scope!r}, node={node!r}, vmid={vmid!r}")

    def list_firewall_rules(self, scope: str = "datacenter",
                            node: str | None = None, vmid: int | None = None) -> list[dict]:
        return self._fw(scope, node, vmid).rules.get()

    def get_firewall_options(self, scope: str = "datacenter",
                             node: str | None = None, vmid: int | None = None) -> dict:
        return self._fw(scope, node, vmid).options.get()

    def set_firewall_options(self, scope: str = "datacenter",
                             node: str | None = None, vmid: int | None = None,
                             **options: Any) -> str:
        return self._fw(scope, node, vmid).options.put(**options)

    def add_firewall_rule(self, action: str, rule_type: str,
                          scope: str = "datacenter", node: str | None = None,
                          vmid: int | None = None, **kwargs: Any) -> str:
        return self._fw(scope, node, vmid).rules.post(
            action=action, type=rule_type, **kwargs
        )

    def update_firewall_rule(self, pos: int, scope: str = "datacenter",
                             node: str | None = None, vmid: int | None = None,
                             **kwargs: Any) -> str:
        return self._fw(scope, node, vmid).rules(pos).put(**kwargs)

    def delete_firewall_rule(self, pos: int, scope: str = "datacenter",
                             node: str | None = None, vmid: int | None = None) -> str:
        return self._fw(scope, node, vmid).rules(pos).delete()

    def list_firewall_ipsets(self, scope: str = "datacenter",
                             node: str | None = None, vmid: int | None = None) -> list[dict]:
        return self._fw(scope, node, vmid).ipset.get()

    def list_firewall_aliases(self, scope: str = "datacenter",
                              node: str | None = None, vmid: int | None = None) -> list[dict]:
        return self._fw(scope, node, vmid).aliases.get()
