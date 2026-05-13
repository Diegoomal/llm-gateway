# jq

`jq` formats and filters JSON in the terminal. It is useful for reading API
responses, extracting fields, and transforming lists without writing a script.

## Install

On Ubuntu or Debian:

```bash
sudo apt install jq
```

Check the installation:

```bash
jq --version
```

## Example

Pretty-print JSON:

```bash
echo '{"name":"llm-gateway","status":"ok"}' | jq
```

Read one field as raw text:

```bash
echo '{"name":"llm-gateway","status":"ok"}' | jq -r '.status'
```
