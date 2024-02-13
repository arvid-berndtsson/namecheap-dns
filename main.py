#!/usr/bin/env python3

import argparse
from itertools import count
import json
from lxml import etree
import requests
import sys
import yaml

namecheap_api_url = "https://api.namecheap.com/xml.response"


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        args (argparse.Namespace): Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Export or import Namecheap " "DNS records"
    )
    parser.add_argument(
        "--config-file",
        action="store",
        default="dns-config.yml",
        help="Config file (default dns-config.yml)",
    )
    subparsers = parser.add_subparsers(title="subcommands", required=True)

    # Import Parser
    import_parser = subparsers.add_parser(
        "import", description="Import records to Namecheap"
    )
    import_parser.set_defaults(command=do_import)
    import_parser.add_argument(
        "--dryrun",
        action="store_true",
        default=False,
        help="Preview changes without " "making them",
    )
    import_parser.add_argument(
        "--input-file",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="File to read records " "from (default stdin)",
    )
    import_parser.add_argument("domain")

    # Export Parser
    export_parser = subparsers.add_parser(
        "export", description="Export records from Namecheap"
    )
    export_parser.set_defaults(command=do_export)
    export_parser.add_argument(
        "--output-file",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="File to write " "records to (default stdout)",
    )
    export_parser.add_argument("domain")

    args = parser.parse_args()
    return args


def make_namecheap_request(config: dict, data: dict) -> etree.Element:
    """
    Makes a request to the Namecheap API using the provided configuration and data.

    Args:
        config (dict): A dictionary containing the API configuration parameters.
        data (dict): A dictionary containing the request data.

    Returns:
        xml.etree.ElementTree.Element: The response XML as an Element object.

    Raises:
        requests.HTTPError: If the request to the Namecheap API fails.
        Exception: If the response from the Namecheap API is not successful.
    """
    request = data.copy()
    request.update(
        {
            "ApiUser": config["ApiUser"],
            "UserName": config["UserName"],
            "ApiKey": config["ApiKey"],
            "ClientIP": config["ClientIP"],
        }
    )
    response = requests.post(namecheap_api_url, request)
    response.raise_for_status()
    response_xml = etree.XML(response.content)
    if response_xml.get("Status") != "OK":
        raise Exception("Bad response: {}".format(response.content))
    return response_xml


def get_records(config: dict, sld, tld) -> list[dict]:
    """
    Retrieves the DNS records for a domain from Namecheap.

    Args:
        config (dict): The configuration settings for making the Namecheap API request.
        sld (str): The second-level domain of the domain.
        tld (str): The top-level domain of the domain.

    Returns:
        list: A list of dictionaries representing the DNS records for the domain.
    """
    response = make_namecheap_request(
        config, {"Command": "namecheap.domains.dns.getHosts",
                 "SLD": sld, "TLD": tld}
    )
    host_elements = response.xpath(
        "/x:ApiResponse/x:CommandResponse/x:DomainDNSGetHostsResult/x:host",
        namespaces={"x": "http://api.namecheap.com/xml.response"},
    )
    records = [dict(h.attrib) for h in host_elements]
    for record in records:
        record.pop("AssociatedAppTitle", None)
        record.pop("FriendlyName", None)
        record.pop("HostId", None)
        record["HostName"] = record.pop("Name")
        record.pop("IsActive", None)
        record.pop("IsDDNSEnabled", None)
        if record["Type"] != "MX":
            record.pop("MXPref", None)
        record["RecordType"] = record.pop("Type")
        if record["TTL"] == "1800":
            record.pop("TTL")
    return records


def do_import(args: argparse.Namespace, config: dict) -> None:
    """
    Import DNS records from an input file and update the DNS records in Namecheap.

    Args:
        args (Namespace): Command-line arguments.
        config (dict): Configuration settings.

    Returns:
        None
    """
    current = get_current(args, config)
    new = get_new(args)

    updated_removed = remove_unused_records(current, new)
    updated_added = add_new_records(current, new)

    if not updated_removed or not updated_added:
        return

    data = {
        "Command": "namecheap.domains.dns.setHosts",
        "SLD": args.sld,
        "TLD": args.tld,
    }

    for num, record in zip(count(1), new.values()):
        for key, value in record.items():
            data[f"{key}{num}"] = value

    if not args.dryrun:
        make_namecheap_request(config, data)

def add_new_records(current: dict[tuple, dict], new: dict) -> bool:
    """
    Adds new records to the current records dictionary.

    Args:
        current (dict[tuple, dict]): The current DNS records represented as a dictionary.
        new (dict): The new DNS records represented as a dictionary.

    Returns:
        bool: True if any new records were added, False otherwise.
    """
    changed = False
    for r in new.keys():
        if r not in current:
            print(f"Adding {new[r]}")
            changed = True
    return changed

def remove_unused_records(current: dict[tuple, dict], new: dict) -> bool:
    """
    Removes unused records from the current DNS records based on the new DNS records.

    Args:
        current (dict[tuple, dict]): The current DNS records represented as a dictionary.
        new (dict): The new DNS records represented as a dictionary.

    Returns:
        bool: True if any unused records were removed, False otherwise.
    """
    changed = False
    for r in current.keys():
        if r not in new:
            print(f"Removing {current[r]}")
            changed = True
    return changed


def get_new(args) -> dict:
    """
    Load new DNS records from an input file and return them as a dictionary.

    Args:
        args (object): The input arguments.

    Returns:
        dict: A dictionary of new DNS records, where the keys are the hash of each record and the values are the records themselves.
    """
    new_records = yaml.safe_load(args.input_file)
    new = {dict_hash(r): r for r in new_records}
    return new


def get_current(args, config) -> dict[tuple, dict]:
    """
    Get the current DNS records from the Namecheap API.

    Args:
        args: The command-line arguments.
        config: The configuration settings.

    Returns:
        A dictionary containing the current DNS records, where the keys are tuples representing the record type and name,
        and the values are dictionaries representing the record details.
    """
    current_records = get_records(config, args.sld, args.tld)
    current = {dict_hash(r): r for r in current_records}
    return current


def do_export(args: argparse.Namespace, config: dict) -> None:
    """
    Export DNS records to a YAML file.

    Args:
        args (Namespace): Command-line arguments.
        config (dict): Configuration settings.

    Returns:
        None
    """
    records = get_records(config, args.sld, args.tld)
    yaml.dump(sorted(records, key=dict_hash), args.output_file)


def dict_hash(d: dict) -> tuple:
    """
    Calculate the hash value for a dictionary.

    Args:
        d (dict): The dictionary to calculate the hash value for.

    Returns:
        tuple: A tuple containing the record type, host name, and JSON representation of the dictionary.

    """
    d = d.copy()
    name = d.pop("HostName")
    type_ = d.pop("RecordType")
    return (type_, name, json.dumps(d, sort_keys=True))


def main() -> None:
    """
    This is the main function that executes the program.
    It parses command line arguments, splits the domain into second-level domain (SLD) and top-level domain (TLD),
    loads the configuration from a file, and executes the specified command.
    """
    args = parse_args()
    (args.sld, args.tld) = args.domain.split(".", 1)
    config: dict = yaml.safe_load(open(args.config_file))
    args.command(args, config)


if __name__ == "__main__":
    main()
