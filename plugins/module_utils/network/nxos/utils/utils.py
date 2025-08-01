from __future__ import absolute_import, division, print_function


__metaclass__ = type
import socket

from functools import total_ordering
from itertools import count, groupby

from ansible.module_utils.six import iteritems


LOGGING_SEVMAP = {
    0: "emergency",
    1: "alert",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notification",
    6: "informational",
    7: "debugging",
}


def search_obj_in_list(name, lst, identifier):
    for o in lst:
        if o[identifier] == name:
            return o
    return None


def flatten_dict(x):
    result = {}
    if not isinstance(x, dict):
        return result

    for key, value in iteritems(x):
        if isinstance(value, dict):
            result.update(flatten_dict(value))
        else:
            result[key] = value

    return result


def validate_ipv4_addr(address):
    address = address.split("/")[0]
    try:
        socket.inet_aton(address)
    except socket.error:
        return False
    return address.count(".") == 3


def validate_ipv6_addr(address):
    address = address.split("/")[0]
    try:
        socket.inet_pton(socket.AF_INET6, address)
    except socket.error:
        return False
    return True


def normalize_interface(name):
    """Return the normalized interface name"""
    if not name:
        return

    def _get_number(name):
        digits = ""
        for char in name:
            if char.isdigit() or char in "/.":
                digits += char
        return digits

    if name.lower().startswith("et"):
        if_type = "Ethernet"
    elif name.lower().startswith("vl"):
        if_type = "Vlan"
    elif name.lower().startswith("lo"):
        if_type = "loopback"
    elif name.lower().startswith("po"):
        if_type = "port-channel"
    elif name.lower().startswith("nv"):
        if_type = "nve"
    else:
        if_type = None

    number_list = name.split(" ")
    if len(number_list) == 2:
        number = number_list[-1].strip()
    else:
        number = _get_number(name)

    if if_type:
        proper_interface = if_type + number
    else:
        proper_interface = name

    return proper_interface


def get_interface_type(interface):
    """Gets the type of interface"""
    if interface.upper().startswith("ET"):
        return "ethernet"
    elif interface.upper().startswith("VL"):
        return "svi"
    elif interface.upper().startswith("LO"):
        return "loopback"
    elif interface.upper().startswith("MG"):
        return "management"
    elif interface.upper().startswith("MA"):
        return "management"
    elif interface.upper().startswith("PO"):
        return "portchannel"
    elif interface.upper().startswith("NV"):
        return "nve"
    else:
        return "unknown"


def remove_rsvd_interfaces(interfaces):
    """Exclude reserved interfaces from user management"""
    if not interfaces:
        return []
    return [i for i in interfaces if get_interface_type(i["name"]) != "management"]


def vlan_range_to_list(vlans):
    result = []
    if vlans:
        for part in vlans.split(","):
            if part == "none":
                break
            if "-" in part:
                a, b = part.split("-")
                a, b = int(a), int(b)
                result.extend(range(a, b + 1))
            else:
                a = int(part)
                result.append(a)
        return numerical_sort(result)
    return result


def numerical_sort(string_int_list):
    """Sorts list of integers that are digits in numerical order."""

    as_int_list = []

    for vlan in string_int_list:
        as_int_list.append(int(vlan))
    as_int_list.sort()
    return as_int_list


def get_logging_sevmap(invert=False):
    x = LOGGING_SEVMAP
    if invert:
        # cannot use dict comprehension yet
        # since we still test with Python 2.6
        x = dict(map(reversed, iteritems(x)))
    return x


def get_ranges(data):
    """
    Returns a generator object that yields lists of
    consequtive integers from a list of integers.
    """
    for _k, group in groupby(data, lambda t, c=count(): int(t) - next(c)):
        yield list(group)


def vlan_list_to_range(cmd):
    """
    Converts a comma separated list of vlan IDs
    into ranges.
    """
    ranges = []
    for v in get_ranges(cmd):
        ranges.append("-".join(map(str, (v[0], v[-1])[: len(v)])))
    return ",".join(ranges)


def generate_switchport_trunk(type, add, vlans_range):
    """
    Generates a list of switchport commands based on the trunk type and VLANs range.
    Ensures that the length of VLANs lexeme in a command does not exceed 220 characters.
    """

    def append_command():
        command_prefix = f"switchport trunk {type} vlan "
        if add or commands:
            command_prefix += "add "
        commands.append(command_prefix + ",".join(current_chunk))

    commands = []
    current_chunk = []
    current_length = 0

    for vrange in vlans_range.split(","):
        next_addition = vrange if not current_chunk else "," + vrange
        if current_length + len(next_addition) <= 220:
            current_chunk.append(vrange)
            current_length += len(next_addition)
        else:
            append_command()
            current_chunk = [vrange]
            current_length = len(vrange)

    if current_chunk:
        append_command()

    return commands


@total_ordering
class Version:
    """Simple class to compare arbitrary versions"""

    def __init__(self, version_string):
        self.components = version_string.split(".")

    def __eq__(self, other):
        other = _coerce(other)
        if not isinstance(other, Version):
            return NotImplemented

        return self.components == other.components

    def __lt__(self, other):
        other = _coerce(other)
        if not isinstance(other, Version):
            return NotImplemented

        return self.components < other.components


def _coerce(other):
    if isinstance(other, str):
        other = Version(other)
    if isinstance(other, (int, float)):
        other = Version(str(other))
    return other
