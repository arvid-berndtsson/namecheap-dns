# Export/import DNS records from/to Namecheap

This script lets you move DNS records from a Namecheap domain to a YAML file or from a YAML file to Namecheap. This is a great way to keep track of your Namecheap DNS records with a change history, almost like having a code for your settings.

But, the Namecheap API doesn't let you make, change, or delete records one by one. It only lets you replace all records for a domain at once. The best way to use this script is to first move all current records to a file. Then, edit this file to add any changes you want. Finally, move the changed file back to Namecheap. 

You should do a test run with `--dryrun` to check everything works.

To use the script, start by [enabling the Namecheap API in your account](https://www.namecheap.com/support/api/intro/#:~:text=com%2Fxml.response-,enabling%20api%20access,-There%20is%20no), make sure to also [whitelist the IPv4 address](https://www.namecheap.com/support/api/intro/#:~:text=Whitelisting%20IP&text=The%20IP%20can%20be%20whitelisted,the%20Business%20%26%20Dev%20Tools%20section.) you are running the script on. This will let the script access your account. 

## Configuration
You need a configuration file. It's usually called `dns-config.yml` and located in the current directory. However, you can use a different file if you specify it on the command line. Here's how the contents of this file should look:
```yml
ApiUser: [Namecheap username]
UserName: [Namecheap username]
ApiKey: [Namecheap API key]
ClientIP: [Public IPv4 address of the host you're running the script on]
```

## YAML file format
The YAML file containing the records looks like this:
```yaml
- Address: 127.0.0.1
  HostName: localhost
  RecordType: A
  TTL: '180'
- Address: 192.168.0.1
  HostName: router
  RecordType: A
- Address: email.my.domain
  MXPref: 10
  HostName: '@'
  RecordType: MX
```
It doesn't matter what order the records or fields in each record are in.

# Usage
The script has a few options. You can see them all with `main.py -h`. Here's a summary:
```shell
main.py [-h] [--config CONFIG]
```
## Import
This command moves all records for a domain to a YAML file. You can use `--dryrun` to see what would happen without actually doing it. You can use `--input-file` to specify a different file to write to.
```shell
main.py import [-h] [--dryrun] [--input-file INPUT_FILE] domain
```
## Export
```shell
main.py export [-h] [--output-file OUTPUT_FILE] domain
```
