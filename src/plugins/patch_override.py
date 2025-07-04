import os
import shutil
import subprocess
import re
from src.log_manager import log
from src.profiler import auto_profile

@auto_profile
class PatchOverride:
    """
    Patch and override operations for PO.
    """
    def __init__(self, vprojects_path, all_projects_info):
        self.vprojects_path = vprojects_path
        self.all_projects_info = all_projects_info

    def po_apply(self, project_name):
        """
        Apply patch and override for the specified project.
        Args:
            project_name (str): Project or board name.
        Returns:
            bool: True if success, otherwise False.
        """
        log.info("start po_apply for project: %s", project_name)
        project_cfg = self.all_projects_info.get(project_name, {})
        board_name = project_cfg.get('board_name')
        if not board_name:
            log.error("Cannot find board name for project: %s", project_name)
            return False
        board_path = os.path.join(self.vprojects_path, board_name)
        po_dir = os.path.join(board_path, "po")
        po_config = project_cfg.get("PROJECT_PO_CONFIG", "").strip()
        if not po_config:
            log.warning("No PROJECT_PO_CONFIG found for %s", project_name)
            return True
        apply_pos, exclude_pos, exclude_files = self.__parse_po_config(po_config)
        apply_pos = [po for po in apply_pos if po not in exclude_pos]
        log.debug("all_projects_info: %s", str(self.all_projects_info.get(project_name, {})))
        log.debug("po_dir: %s", po_dir)
        if apply_pos:
            log.debug("apply_pos: %s", str(apply_pos))
        if exclude_pos:
            log.debug("exclude_pos: %s", str(exclude_pos))
        if exclude_files:
            log.debug("exclude_files: %s", str(exclude_files))
        for po in apply_pos:
            po_patch_dir = os.path.join(po_dir, po, "patches")
            if not self.__apply_patch(po, po_patch_dir, exclude_files):
                log.error("PO apply aborted due to patch error in PO: %s", po)
                return False
            po_override_dir = os.path.join(po_dir, po, "overrides")
            if not self.__apply_override(po, po_override_dir, exclude_files):
                log.error("PO apply aborted due to override error in PO: %s", po)
                return False
            log.info("po %s has been processed", po)
        log.info("po apply finished for project: %s", project_name)
        return True

    def __parse_po_config(self, po_config):
        apply_pos = []
        exclude_pos = set()
        exclude_files = {}
        tokens = re.findall(r'-?\w+(?:\[[^\]]+\])?', po_config)
        for token in tokens:
            if token.startswith('-'):
                if '[' in token:
                    po, files = re.match(r'-(\w+)\[([^\]]+)\]', token).groups()
                    file_list = set(f.strip() for f in files.split())
                    exclude_files.setdefault(po, set()).update(file_list)
                else:
                    po = token[1:]
                    exclude_pos.add(po)
            else:
                po = token
                apply_pos.append(po)
        return apply_pos, exclude_pos, exclude_files

    def __apply_patch(self, po, po_patch_dir, exclude_files):
        patch_applied_dirs = set()
        log.debug("po=%s, po_patch_dir=%s", po, po_patch_dir)
        if not os.path.isdir(po_patch_dir):
            log.debug("No patches dir for PO: %s", po)
            return True
        log.debug("applying patches for po: %s", po)
        for root, _, files in os.walk(po_patch_dir):
            for fname in files:
                if fname == ".gitkeep":
                    # log.debug("ignore .gitkeep file in %s", root)
                    continue
                rel_path = os.path.relpath(os.path.join(root, fname), po_patch_dir)
                log.debug("patch rel_path: %s", rel_path)
                if po in exclude_files and rel_path in exclude_files[po]:
                    log.debug("patch file %s in po %s is excluded by config", rel_path, po)
                    continue
                top_dir = rel_path.split(os.sep)[0]
                patch_flag = os.path.join(top_dir, ".patch_applied")
                log.debug("patch top_dir: %s, patch_flag: %s", top_dir, patch_flag)
                if top_dir in patch_applied_dirs:
                    log.debug("patch flag already set for dir: %s, skipping", top_dir)
                    continue
                if os.path.exists(patch_flag):
                    log.info("patch already applied for dir: %s, skipping", top_dir)
                    patch_applied_dirs.add(top_dir)
                    continue
                patch_file = os.path.join(root, fname)
                log.info("applying patch: %s to dir: %s", patch_file, top_dir)
                try:
                    result = subprocess.run([
                        "git", "apply", patch_file
                    ], cwd=".", capture_output=True, text=True, check=False)
                    log.debug("git apply result: returncode=%s, stdout=%s, stderr=%s", result.returncode, result.stdout, result.stderr)
                    if result.returncode != 0:
                        log.error("Failed to apply patch %s: %s", patch_file, result.stderr)
                        return False
                    with open(patch_flag, 'w', encoding='utf-8') as f:
                        f.write('patch applied')
                    patch_applied_dirs.add(top_dir)
                    log.info("patch applied and flag set for dir: %s", top_dir)
                except subprocess.SubprocessError as e:
                    log.error("Subprocess error applying patch %s: %s", patch_file, e)
                    return False
                except OSError as e:
                    log.error("OS error applying patch %s: %s", patch_file, e)
                    return False
        return True

    def __apply_override(self, po, po_override_dir, exclude_files):
        override_applied_dirs = set()
        log.debug("po=%s, po_override_dir=%s", po, po_override_dir)
        if not os.path.isdir(po_override_dir):
            log.debug("No overrides dir for PO: %s", po)
            return True
        log.debug("applying overrides for po: %s", po)
        for root, _, files in os.walk(po_override_dir):
            for fname in files:
                if fname == ".gitkeep":
                    # log.debug("ignore .gitkeep file in %s", root)
                    continue
                rel_path = os.path.relpath(os.path.join(root, fname), po_override_dir)
                log.debug("override rel_path: %s", rel_path)
                if po in exclude_files and rel_path in exclude_files[po]:
                    log.debug("override file %s in po %s is excluded by config", rel_path, po)
                    continue
                top_dir = rel_path.split(os.sep)[0]
                override_flag = os.path.join(top_dir, ".override_applied")
                log.debug("override top_dir: %s, override_flag: %s", top_dir, override_flag)
                if top_dir in override_applied_dirs:
                    log.debug("override flag already set for dir: %s, skipping", top_dir)
                    continue
                if os.path.exists(override_flag):
                    log.info("override already applied for dir: %s, skipping", top_dir)
                    override_applied_dirs.add(top_dir)
                    continue
                src_file = os.path.join(root, fname)
                dest_file = os.path.join(top_dir, *rel_path.split(os.sep)[1:]) if len(rel_path.split(os.sep)) > 1 else os.path.join(top_dir, fname)
                log.debug("override src_file: %s, dest_file: %s", src_file, dest_file)
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                try:
                    shutil.copy2(src_file, dest_file)
                    with open(override_flag, 'w', encoding='utf-8') as f:
                        f.write('override applied')
                    override_applied_dirs.add(top_dir)
                    log.info("override applied and flag set for dir: %s, file: %s", top_dir, dest_file)
                except OSError as e:
                    log.error("Failed to copy override file %s to %s: %s", src_file, dest_file, e)
                    return False
        return True 