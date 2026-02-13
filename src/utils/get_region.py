import json
import os


# This loads the region mapping from region-wise-state.json once.
_region_data = None
_region_file_path = os.path.join(os.path.dirname(__file__), '..', 'region-wise-state.json')

def get_region_data():
    """Loads and caches the state-to-region mapping from the JSON file."""
    global _region_data
    if _region_data is None:
        try:
            with open(_region_file_path, 'r') as f:
                # The JSON is a list with one object: [{"region": ["state1", "state2"], ...}]
                # We need to invert it to {"state": "region"} for efficient lookups.
                region_to_states_list = json.load(f)
                if region_to_states_list:
                    region_to_states = region_to_states_list[0]
                    _region_data = {
                        state.lower(): region 
                        for region, states in region_to_states.items() 
                        for state in states
                    }
        except (FileNotFoundError, json.JSONDecodeError):
            _region_data = {}
    return _region_data



_region_states_by_region = None

def get_states_by_region(region_name: str) -> list:
    """Returns the list of states for a given region name from the JSON file."""
    global _region_states_by_region
    if _region_states_by_region is None:
        try:
            with open(_region_file_path, 'r') as f:
                region_to_states_list = json.load(f)
                if region_to_states_list:
                    # region_to_states is: {"south": [...], "west": [...]}
                    _region_states_by_region = region_to_states_list[0]
        except (FileNotFoundError, json.JSONDecodeError):
            _region_states_by_region = {}

    # Defensive: use lower-case key for matching input
    return _region_states_by_region.get(region_name.lower(), [])


