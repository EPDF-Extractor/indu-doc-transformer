from typing import Any
from indu_doc.common_utils import normalize_string
from indu_doc.god import God

from indu_doc.connection import Connection
from indu_doc.lark_parser import run_parser
from indu_doc.xtarget import XTarget
import logging
logger = logging.getLogger(__name__)

def _merge_search_tree(tree: dict[str, Any], data: Any, path: list[str] | None = None) -> None:
    if path is None:
        path = []
    if isinstance(data, dict):
        for key, value in data.items():
            norm_key = normalize_string(str(key))
            branch = tree.setdefault(norm_key, {})
            _merge_search_tree(branch, value, path + [norm_key])
    elif isinstance(data, list):
        list_branch = tree.setdefault('[list items]', {})
        param_displays: set[str] = set()
        for item in data:
            if isinstance(item, dict):
                candidate = item.get('name') or item.get('key') or item.get('tag')
                if isinstance(candidate, str):
                    display = candidate.strip() or normalize_string(candidate)
                    unit = item.get('unit') or item.get('units')
                    if isinstance(unit, str) and unit.strip():
                        display = f'{display} [{unit.strip()}]'
                    else:
                        value_str = item.get('value')
                        if isinstance(value_str, str) and value_str.strip():
                            display = f'{display} {value_str.strip()}'
                    param_displays.add(display)
            _merge_search_tree(list_branch, item, path)
        if path:
            # Add filters for items if any
            if param_displays:
                item_filters = list_branch.setdefault('__filters__', set())
                for display in sorted(param_displays, key=str.lower):
                    item_filters.add(f"@{'.'.join(path)}({display})")
    else:
        if path:
            if len(path) > 1:
                filters = tree.setdefault('__filters__', set())
                filters.add(f"@{'.'.join(path[:-1])}({path[-1]})")
            else:
                tree.setdefault('__filters__', set()).add(f"@{'.'.join(path)}")


class Searcher:
    def __init__(self, god: God, init_index: list[str]=[]) -> None:
        self.god = god
        self.xtargets_index: dict[str, dict[str, Any]] = {}
        self.connections_index: dict[str, dict[str, Any]] = {}
        if "conns" in init_index:
            self.index_connections(self.god.connections)
        if "targets" in init_index:
            self.index_targets(self.god.xtargets)

    def start_indexing(self) -> None:
        pass
    
    def index_targets(self, targets: dict[str, XTarget]):
        for guid, target in targets.items():
            ind_obj = target.to_dict()

            self.xtargets_index[guid] = ind_obj

    def index_connections(self, connections: dict[str, Connection] ):
        for guid, conn in connections.items():
            ind_obj = conn.to_dict()
            # add special fields for connection
            ind_obj['tag'] = conn.through.tag.tag_str if conn.through else ""
            ind_obj['src'] = conn.src.tag.tag_str if conn.src else ""
            ind_obj['dest'] = conn.dest.tag.tag_str if conn.dest else ""
            self.connections_index[guid] = ind_obj
    
    def __partial_match(self, text: str, q: str) -> bool:
        return normalize_string(q) in normalize_string(text)
    
    def search_targets(self, query: str) -> list[str]:
        """
        returns list of guids of xtargets matching the query
        """
        tag , filters = run_parser(query)
        results = []
        for guid, target in self.xtargets_index.items():
            if tag and not self.__partial_match(target['tag'], tag):
                continue
            # apply filters
            match = True
            print(f"Filtering target {guid} with filters: {filters}")
            for f in filters:
                path, param, value = f.dotted_path, f.dotted_param, f.value
                
                # Check if the path leads to a matching value
                if not self._check_path_match(target, path, param, value):
                    match = False
                    break
                    
            if match:
                results.append(guid)
        return results
    
    
    def search_connections(self, query: str) -> list[str]:
        """
        returns list of guids of connections matching the query
        """
        tag , filters = run_parser(query)
        results = []
        for guid, conn in self.connections_index.items():
            if tag and not self.__partial_match(conn['tag'], tag):
                continue
            # apply filters
            match = True
            for f in filters:
                path, param, value = f.dotted_path, f.dotted_param, f.value
                logger.info(f"Filtering connection {guid}: path={path}, param={param}, value={value}")
                
                # Check if the path leads to a matching value
                if not self._check_path_match(conn, path, param, value):
                    match = False
                    break
                    
            if match:
                results.append(guid)
        return results
    
    def _check_path_match(self, data: Any, path: list[str], param: str | None, value: str | None) -> bool:
        """Check if the given path matches in the data structure, handling lists properly."""
        current = data
        
        for i, p in enumerate(path):
            p = normalize_string(p)
            
            if isinstance(current, dict):
                if p not in current:
                    return False
                current = current[p]
            elif isinstance(current, list):
                # If we encounter a list, check if any item matches the remaining path
                remaining_path = path[i:]
                return any(self._check_path_match(item, remaining_path, param, value) for item in current)
            else:
                return False
        
        # Now current should be the final value to check
        if isinstance(current, dict) and param:
            param = normalize_string(param)
            if param in current:
                current = current[param]
            else:
                return False
        elif isinstance(current, list) and param:
            param = normalize_string(param)
            found = any(isinstance(item, dict) and param in item and (value is None or self.__partial_match(str(item[param]), value)) for item in current)
            return found
        elif param:
            return False
            
        # Final value check
        if value is not None:
            return self.__partial_match(str(current), value)
        return True
    
    def create_target_search_guide_tree(self) -> dict[str, Any]:
        """
        Go through all targets and create a tree structure based on dict representation
        So user can see what fields are available for searching
        """
        tree: dict[str, Any] = {}
        for target in self.xtargets_index.values():
            _merge_search_tree(tree, target)
        return tree

    def create_connection_search_guide_tree(self) -> dict[str, Any]:
        """
        Go through all connections and create a tree structure based on dict representation
        So user can see what fields are available for searching
        """
        tree: dict[str, Any] = {}
        for conn in self.connections_index.values():
            _merge_search_tree(tree, conn)
        return tree
