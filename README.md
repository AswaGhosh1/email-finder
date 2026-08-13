# 📧 Email Finder

[![Python Version](https://img.shields.io/badge/python-3.6+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/AswaGhosh1/email-finder.svg)](https://github.com/AswaGhosh1/email-finder/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/AswaGhosh1/email-finder.svg)](https://github.com/AswaGhosh1/email-finder/issues)

> Interactive email discovery tool that finds corporate email addresses by testing common patterns against SMTP servers.

---

## ✨ Features

- 🔍 **Single name lookup** - Quick verification for one person
- 📁 **Batch processing** - Process hundreds of names from a file with TAB completion
- 🌐 **Automatic domain discovery** - Tries multiple extensions (.com, .co.in, .in, .org, .net, .io, etc.)
- 🏳️ **Smart country detection** - Prioritizes country-specific domains (.co.in for India, .co.uk for UK, etc.)
- 🛡️ **Catch-all detection** - Identifies domains that accept all addresses
- 💾 **Results saved** - Automatically saves found emails to `found_emails.txt`
- ⚡ **Fast SMTP verification** - Direct RCPT TO checks
- 🔄 **TAB completion** - Auto-complete file paths in batch mode

---

## 📦 Installation

### From GitHub (Recommended)

```bash
git clone https://github.com/AswaGhosh1/email-finder.git
cd email-finder
pip install -e .
```

### For Kali Linux

```bash
git clone https://github.com/AswaGhosh1/email-finder.git
cd email-finder
pip install -e . --break-system-packages
```

## 🚀 Usage

### Interactive Mode

```bash
email-finder
```

### Single Name Lookup

```bash
email-finder --single "John Smith" "Google"
```

### Batch Mode

```bash
# Create a names file
echo "John Smith" > names.txt
echo "Jane Doe" >> names.txt

# Run batch mode
email-finder --batch names.txt "Microsoft"
```

### Help & Version

```bash
email-finder --help
email-finder --version
```

## 📊 Example Output

```bash
$ email-finder --single "John Smith" "Google"

[*] Searching for valid domain for: Google
[*] Detected possible country: US
[*] Testing 21 domain variants...
[+] Found valid domain: google.com

[+] Using domain: google.com
[*] Looking up MX record for google.com...
[+] Using mail server: mail.google.com

[*] Checking whether domain is catch-all...
[*] Testing 12 possible email patterns for John Smith...

[+] Valid email found: john.smith@google.com
```

## 🔧 Requirements

- Python 3.6+
- dnspython library

## 📄 License

This project is licensed under the MIT License.

## 👤 Author

**AswaGhosh1**
- GitHub: [@AswaGhosh1](https://github.com/AswaGhosh1)

## ⭐ Support

If you find this tool useful, please give it a ⭐ on GitHub!

## 🔒 Disclaimer

This tool is for educational and legitimate business purposes only.

---

**Made with ❤️ by AswaGhosh1**
