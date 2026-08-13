#!/usr/bin/env python3
"""
email-finder - Interactive email finder

Prompts for a person's full name and their company's domain, generates the
most common corporate email address patterns, and tests each one via direct
SMTP RCPT TO checks (same technique as verify_email.py) to find which one
is likely real.

Supports single name lookup or bulk processing from a text file.
Automatically tries multiple domain extensions for a company name.

Usage:
    email-finder                    # Run interactively
    email-finder --help             # Show this help message
    python3 -m email_finder         # Alternative run command

Requires: dnspython (pip install dnspython --break-system-packages)
"""

import re
import smtplib
import socket
import sys
import time
import os
import argparse
from typing import List, Dict, Tuple, Optional
from pathlib import Path

try:
    import dns.resolver
except ImportError:
    print("[-] Missing dependency 'dnspython'. Install with:")
    print("    pip install dnspython --break-system-packages")
    sys.exit(1)

# Try to import prompt_toolkit for better input with tab completion
try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import Completer, Completion
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


# Version
__version__ = "1.0.0"


# Common domain extensions to try
COMMON_EXTENSIONS = [
    '.com',
    '.co.in',
    '.in',
    '.org',
    '.net',
    '.io',
    '.ai',
    '.tech',
    '.co',
    '.uk',
    '.eu',
    '.de',
    '.fr',
    '.ca',
    '.au',
    '.jp',
    '.cn',
    '.br',
    '.mx',
    '.sg',
    '.hk'
]

# Country-specific extensions
COUNTRY_EXTENSIONS = {
    'us': ['.com', '.us', '.co', '.org'],
    'in': ['.co.in', '.in', '.com', '.org', '.net'],
    'uk': ['.co.uk', '.uk', '.com', '.org'],
    'ca': ['.ca', '.com', '.org', '.net'],
    'au': ['.com.au', '.au', '.com', '.org'],
    'de': ['.de', '.com', '.org'],
    'fr': ['.fr', '.com', '.org'],
    'jp': ['.co.jp', '.jp', '.com', '.org'],
    'cn': ['.com.cn', '.cn', '.com', '.org'],
    'br': ['.com.br', '.br', '.com', '.org'],
    'mx': ['.com.mx', '.mx', '.com', '.org'],
    'sg': ['.com.sg', '.sg', '.com', '.org'],
    'hk': ['.com.hk', '.hk', '.com', '.org'],
}


# File path completer for prompt_toolkit
class FilePathCompleter(Completer):
    """File path completer for prompt_toolkit."""
    def get_completions(self, document, complete_event):
        text = document.text
        if not text:
            text = '.'

        # Get the directory and partial file name
        if '/' in text:
            last_slash = text.rfind('/')
            if last_slash == -1:
                dirname = '.'
                basename = text
            else:
                dirname = text[:last_slash] if last_slash > 0 else '.'
                basename = text[last_slash + 1:]
        else:
            dirname = '.'
            basename = text

        # Expand user home directory
        if dirname.startswith('~'):
            dirname = os.path.expanduser(dirname)

        try:
            if os.path.exists(dirname) and os.path.isdir(dirname):
                items = sorted(os.listdir(dirname))
                for item in items:
                    if item.lower().startswith(basename.lower()):
                        full_path = os.path.join(dirname, item)
                        if os.path.isdir(full_path):
                            completion_text = item + '/'
                        else:
                            completion_text = item

                        display = os.path.join(dirname, item) if dirname != '.' else item
                        if os.path.isdir(full_path):
                            display += '/'

                        yield Completion(
                            completion_text,
                            start_position=-len(basename),
                            display=display
                        )
        except Exception:
            pass


def input_simple(prompt_text: str) -> str:
    """Simple input function with keyboard interrupt handling."""
    try:
        if PROMPT_TOOLKIT_AVAILABLE:
            return pt_prompt(prompt_text)
        else:
            return input(prompt_text)
    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user.")
        sys.exit(0)
    except EOFError:
        print("\n\n[!] Input stream closed. Exiting...")
        sys.exit(0)


def clean_company_name(raw: str) -> str:
    """
    Clean company name by removing common words and special characters.
    """
    # Remove common suffixes
    raw = re.sub(r'\s+(Inc|Ltd|LLC|LLP|Pvt|Private|Limited|Corp|Corporation|Co|Company|Technologies|Tech|Solutions|Systems|Software|Services|Group|Holdings|Enterprises|Ventures|Labs|Studios|Media|Global|International|Digital|Creative|Design|Consulting|Partners|Associates|Alliance|Network|Platforms|Industries)\b', '', raw, flags=re.IGNORECASE)

    # Remove special characters and extra spaces
    raw = re.sub(r'[^\w\s]', ' ', raw)
    raw = re.sub(r'\s+', ' ', raw).strip()

    # Convert to lowercase
    raw = raw.lower()

    # Replace spaces with nothing (for domain)
    return raw.replace(' ', '')


def generate_domain_variants(company_name: str, country_hint: Optional[str] = None) -> List[str]:
    """
    Generate possible domain variants for a company name.
    """
    cleaned = clean_company_name(company_name)
    variants = []

    # If company name already contains a domain extension, use it as-is
    if any(ext in cleaned for ext in ['.com', '.co', '.in', '.org', '.net', '.io']):
        if not cleaned.startswith('http'):
            return [cleaned]

    # Get extensions to try
    extensions = COMMON_EXTENSIONS
    if country_hint and country_hint in COUNTRY_EXTENSIONS:
        extensions = COUNTRY_EXTENSIONS[country_hint] + [ext for ext in COMMON_EXTENSIONS if ext not in COUNTRY_EXTENSIONS[country_hint]]

    # Generate variants
    for ext in extensions:
        variants.append(f"{cleaned}{ext}")

    # Also try with hyphenated versions for multi-word companies
    if ' ' in company_name:
        hyphenated = company_name.lower().replace(' ', '-')
        hyphenated = clean_company_name(hyphenated)
        for ext in extensions[:5]:
            variants.append(f"{hyphenated}{ext}")

    # Try with the first letter of each word (e.g., IBM)
    words = company_name.lower().split()
    if len(words) > 1:
        acronym = ''.join(word[0] for word in words if word)
        for ext in extensions[:5]:
            variants.append(f"{acronym}{ext}")

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)

    return unique


def detect_country_hint(company_name: str) -> Optional[str]:
    """
    Try to detect country hint from company name or common patterns.
    """
    company_lower = company_name.lower()

    # Check for common country indicators
    if 'india' in company_lower or 'indian' in company_lower:
        return 'in'
    elif 'usa' in company_lower or 'us' in company_lower or 'american' in company_lower:
        return 'us'
    elif 'uk' in company_lower or 'british' in company_lower or 'england' in company_lower:
        return 'uk'
    elif 'canada' in company_lower or 'canadian' in company_lower:
        return 'ca'
    elif 'australia' in company_lower or 'australian' in company_lower:
        return 'au'
    elif 'germany' in company_lower or 'german' in company_lower:
        return 'de'
    elif 'france' in company_lower or 'french' in company_lower:
        return 'fr'
    elif 'japan' in company_lower or 'japanese' in company_lower:
        return 'jp'
    elif 'china' in company_lower or 'chinese' in company_lower:
        return 'cn'
    elif 'brazil' in company_lower or 'brazilian' in company_lower:
        return 'br'
    elif 'mexico' in company_lower or 'mexican' in company_lower:
        return 'mx'
    elif 'singapore' in company_lower:
        return 'sg'
    elif 'hong kong' in company_lower:
        return 'hk'

    return None


def find_valid_domain(company_name: str, timeout: int = 3) -> Tuple[Optional[str], List[str]]:
    """
    Find a valid domain for a company by trying multiple extensions.
    Returns (found_domain, list_of_tried_variants)
    """
    print(f"[*] Searching for valid domain for: {company_name}")

    # Detect country hint
    country_hint = detect_country_hint(company_name)
    if country_hint:
        print(f"[*] Detected possible country: {country_hint.upper()}")

    # Generate domain variants
    variants = generate_domain_variants(company_name, country_hint)
    print(f"[*] Testing {len(variants)} domain variants...")

    tried = []

    # If user provided a specific domain-like string, try it first
    if '.' in company_name and not company_name.startswith('http'):
        cleaned = clean_domain(company_name)
        tried.append(cleaned)
        mx = get_mx_server(cleaned, timeout)
        if mx:
            print(f"[+] Found valid domain: {cleaned}")
            return cleaned, tried

    # Try each variant silently
    for variant in variants:
        tried.append(variant)
        mx = get_mx_server(variant, timeout)
        if mx:
            print(f"[+] Found valid domain: {variant}")
            return variant, tried

    print(f"\n[-] No valid domain found for '{company_name}'")
    return None, tried


def get_mx_server(domain, timeout=5):
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout
        answers = resolver.resolve(domain, "MX")
        sorted_mx = sorted(answers, key=lambda r: r.preference)
        return str(sorted_mx[0].exchange).rstrip(".")
    except Exception:
        return None


def clean_domain(raw):
    """Turn 'https://www.acme.com/about' or 'Acme.com' into 'acme.com'."""
    raw = raw.strip().lower()
    raw = re.sub(r"^https?://", "", raw)
    raw = re.sub(r"^www\.", "", raw)
    raw = raw.split("/")[0]
    return raw


def split_name(full_name):
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    first = parts[0]
    last = parts[-1]
    return first, last


def generate_candidates(first, last, domain, include_numeric_suffixes=True):
    first = re.sub(r"[^a-z]", "", first.lower())
    last = re.sub(r"[^a-z]", "", last.lower())
    f = first[0] if first else ""
    l = last[0] if last else ""

    patterns = []
    if first and last:
        patterns = [
            f"{first}.{last}@{domain}",
            f"{first}{last}@{domain}",
            f"{f}{last}@{domain}",
            f"{first}{l}@{domain}",
            f"{first}@{domain}",
            f"{last}@{domain}",
            f"{first}_{last}@{domain}",
            f"{last}.{first}@{domain}",
            f"{f}.{last}@{domain}",
            f"{last}{f}@{domain}",
        ]
    elif first:
        patterns = [f"{first}@{domain}"]

    # Numeric variations for common names
    if include_numeric_suffixes and first:
        base_forms = []
        if first and last:
            base_forms = [f"{first}.{last}", f"{first}{last}"]
        else:
            base_forms = [first]
        for base in base_forms:
            for n in ["1", "2", "3", "01", "02"]:
                patterns.append(f"{base}{n}@{domain}")

    # de-dupe while preserving order
    seen = set()
    unique = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def verify_email_smtp(mx_server, email, mail_from="verify@local-tool.com",
                       helo_domain="localhost", timeout=5):
    result = {"email": email, "status": "error", "code": None, "message": ""}
    try:
        server = smtplib.SMTP(mx_server, 25, timeout=timeout)
        server.helo(helo_domain)

        # Try STARTTLS if available
        try:
            server.starttls()
            server.helo(helo_domain)
        except:
            pass

        server.mail(mail_from)
        code, message = server.rcpt(email)
        server.quit()

        decoded_msg = message.decode("utf-8", errors="ignore").strip() if isinstance(message, bytes) else str(message)
        result["code"] = code
        result["message"] = decoded_msg
        result["status"] = "valid" if code == 250 else "invalid"
        return result
    except (socket.timeout, ConnectionRefusedError, smtplib.SMTPException, OSError) as e:
        result["message"] = str(e)
        return result
    except Exception as e:
        result["message"] = str(e)
        return result


def check_catch_all(mx_server, domain, mail_from="verify@local-tool.com",
                     helo_domain="localhost", timeout=5):
    fake_email = f"completelyfake123456789@{domain}"
    result = verify_email_smtp(mx_server, fake_email, mail_from, helo_domain, timeout)
    return result["status"] == "valid"


def process_single_name(full_name: str, domain: str, mx_server: str, verbose: bool = True) -> Optional[str]:
    """Process a single name and return the found email if any."""
    first, last = split_name(full_name)
    candidates = generate_candidates(first, last, domain)

    if not candidates:
        if verbose:
            print(f"[-] Could not generate any candidate patterns for '{full_name}'.")
        return None

    if verbose:
        print(f"[*] Testing {len(candidates)} possible email patterns for {full_name}...")

    for email in candidates:
        result = verify_email_smtp(mx_server, email, timeout=5)
        if result["status"] == "valid":
            return email
        time.sleep(0.5)

    return None


def get_file_path_from_user(prompt_text: str) -> Optional[str]:
    """
    Get file path from user with tab completion using prompt_toolkit.
    """
    try:
        if PROMPT_TOOLKIT_AVAILABLE:
            completer = FilePathCompleter()
            file_path = pt_prompt(f"\n{prompt_text}", completer=completer)
        else:
            file_path = input(f"\n{prompt_text}")
    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user.")
        sys.exit(0)
    except EOFError:
        print("\n\n[!] Input stream closed. Exiting...")
        sys.exit(0)

    if not file_path:
        return None

    # Clean the path
    file_path = file_path.strip('"\'')

    # Expand user home directory
    if file_path.startswith('~'):
        file_path = os.path.expanduser(file_path)

    path = Path(file_path)

    if path.exists() and path.is_file():
        return str(path.absolute())

    print(f"\n[-] File not found: {path.absolute()}")
    print("[!] Make sure the file exists and you have read permissions.")

    retry = input("\nTry again? (y/n): ").strip().lower()
    if retry == 'y':
        return get_file_path_from_user(prompt_text)
    return None


def load_names_from_file(filename: str) -> List[str]:
    """Load names from a text file (one per line)."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            names = [line.strip() for line in f if line.strip()]
        return names
    except Exception as e:
        print(f"[-] Error reading file: {e}")
        return []


def save_results_to_file(results: Dict[str, Optional[str]], domain: str, output_file: str = "found_emails.txt"):
    """Save found emails to a file."""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# Email Finder Results for {domain}\n")
            f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            found_count = 0
            for name, email in results.items():
                if email:
                    f.write(f"{email}\n")
                    found_count += 1

            f.write(f"\n# Total found: {found_count} out of {len(results)} names\n")
        print(f"[+] Results saved to {output_file}")
    except Exception as e:
        print(f"[-] Error saving results: {e}")


def print_summary(results: Dict[str, Optional[str]]):
    """Print a summary of results."""
    total = len(results)
    found = sum(1 for email in results.values() if email)
    not_found = total - found

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total names processed: {total}")
    print(f"Emails found: {found}")
    print(f"Not found: {not_found}")

    if found > 0:
        print("\nFound emails:")
        for name, email in results.items():
            if email:
                print(f"  ✅ {name} -> {email}")

    if not_found > 0:
        print("\nNot found:")
        for name, email in results.items():
            if not email:
                print(f"  ❌ {name}")
    print("=" * 50)


def interactive_mode():
    """Run the interactive single-name mode."""
    print("\n" + "=" * 50)
    print("SINGLE NAME MODE")
    print("=" * 50)

    full_name = input_simple("\nEnter full name: ").strip()
    if not full_name:
        print("[-] Name is required.")
        return

    company_name = input_simple("Enter company name: ").strip()
    if not company_name:
        print("[-] Company name is required.")
        return

    process_single_with_company(full_name, company_name)


def batch_mode():
    """Run the batch mode with a file of names."""
    print("\n" + "=" * 50)
    print("BATCH MODE")
    print("=" * 50)

    # Get file path with tab completion
    file_path = get_file_path_from_user("Enter path to names file (one name per line): ")
    if not file_path:
        print("[-] No file provided. Aborting.")
        return

    names = load_names_from_file(file_path)
    if not names:
        return

    print(f"\n[+] Loaded {len(names)} names from file.")

    # Get company name
    company_name = input_simple("\nEnter company name: ").strip()
    if not company_name:
        print("[-] Company name is required.")
        return

    # Find valid domain
    domain, _ = find_valid_domain(company_name)
    if not domain:
        print("[-] Could not find a valid domain for this company. Aborting.")
        return

    print(f"\n[+] Using domain: {domain}")

    # Get MX server
    print(f"[*] Looking up MX record for {domain}...")
    mx_server = get_mx_server(domain)
    if not mx_server:
        print("[-] Could not find a mail server for this domain. Aborting.")
        return
    print(f"[+] Using mail server: {mx_server}\n")

    # Check for catch-all
    print("[*] Checking whether domain is catch-all...")
    if check_catch_all(mx_server, domain):
        print("[!] This domain accepts ALL addresses (catch-all). SMTP verification")
        print("    won't reliably tell real addresses from fake ones for this domain.")
        print("    Showing the most statistically likely pattern as a best guess:\n")

        results = {}
        for name in names:
            first, last = split_name(name)
            candidates = generate_candidates(first, last, domain)
            results[name] = candidates[0] if candidates else None

        print_summary(results)

        save_option = input_simple("\nSave results to file? (y/n): ").strip().lower()
        if save_option == 'y':
            save_results_to_file(results, domain)
        return

    # Process all names
    print(f"[*] Processing {len(names)} names...\n")
    results = {}

    for i, name in enumerate(names, 1):
        print(f"[{i}/{len(names)}] Testing '{name}'...")
        email = process_single_name(name, domain, mx_server, verbose=False)
        results[name] = email

        if email:
            print(f"  ✅ Found: {email}")
        else:
            print(f"  ❌ No match found")
        print()

    print_summary(results)

    save_option = input_simple("\nSave results to file? (y/n): ").strip().lower()
    if save_option == 'y':
        save_results_to_file(results, domain)


def process_single_with_company(full_name: str, company_name: str):
    """Process a single name with company name."""
    domain, _ = find_valid_domain(company_name)
    if not domain:
        print("[-] Could not find a valid domain for this company. Aborting.")
        return

    print(f"\n[+] Using domain: {domain}")

    print(f"[*] Looking up MX record for {domain}...")
    mx_server = get_mx_server(domain)
    if not mx_server:
        print("[-] Could not find a mail server for this domain. Aborting.")
        return
    print(f"[+] Using mail server: {mx_server}\n")

    print("[*] Checking whether domain is catch-all...")
    if check_catch_all(mx_server, domain):
        print("[!] This domain accepts ALL addresses (catch-all). SMTP verification")
        print("    won't reliably tell real addresses from fake ones for this domain.")
        print("    Showing the most statistically likely pattern as a best guess:\n")
        first, last = split_name(full_name)
        candidates = generate_candidates(first, last, domain)
        if candidates:
            print(f"    Best guess: {candidates[0]}")
        return

    email = process_single_name(full_name, domain, mx_server, verbose=True)

    print()
    if email:
        print(f"[+] Valid email found: {email}")
    else:
        print("[-] None of the common patterns came back as valid.")
        print("    The person may use an uncommon pattern, or the server may not")
        print("    reveal validity at this stage (common with Gmail/Outlook).")


def show_help():
    """Show help information."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    EMAIL FINDER TOOL                        ║
║                    Version 1.0.0                            ║
╚══════════════════════════════════════════════════════════════╝

DESCRIPTION:
    An OSINT interactive email discovery tool that finds corporate email
    addresses by testing common patterns against SMTP servers.

USAGE:
    email-finder              # Run in interactive mode

COMMANDS:
    No commands needed - just run the tool and follow the prompts!

FEATURES:
    • Single name lookup
    • Batch processing from text file with TAB completion
    • Automatic domain discovery
    • Smart country detection
    • Catch-all domain detection
    • Results saved to file

EXAMPLES:
    # Single name lookup
    $ email-finder
    > Select mode: 1
    > Enter full name: John Smith
    > Enter company name: Google

REQUIREMENTS:
    Python 3.6+
    dnspython library

MORE INFO:
    GitHub: https://github.com/AswaGhosh1/email-finder
    """)


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="Email Finder - Discover corporate email addresses",
        add_help=False
    )
    parser.add_argument('--help', action='store_true', help='Show this help message')
    parser.add_argument('--version', action='store_true', help='Show version information')
    parser.add_argument('--single', nargs=2, metavar=('NAME', 'COMPANY'),
                       help='Single name lookup (e.g., --single "John Smith" "Google")')
    parser.add_argument('--batch', nargs=2, metavar=('FILE', 'COMPANY'),
                       help='Batch mode (e.g., --batch names.txt "Microsoft")')

    args = parser.parse_args()

    if args.help:
        show_help()
        return

    if args.version:
        print(f"Email Finder v{__version__}")
        return

    if args.single:
        name, company = args.single
        print("=== Email Finder ===\n")
        process_single_with_company(name, company)
        return

    if args.batch:
        file_path, company = args.batch
        print("=== Email Finder ===\n")
        print("=" * 50)
        print("BATCH MODE")
        print("=" * 50)

        names = load_names_from_file(file_path)
        if not names:
            return

        print(f"[+] Loaded {len(names)} names from file.")

        domain, _ = find_valid_domain(company)
        if not domain:
            print("[-] Could not find a valid domain for this company. Aborting.")
            return

        print(f"\n[+] Using domain: {domain}")

        print(f"[*] Looking up MX record for {domain}...")
        mx_server = get_mx_server(domain)
        if not mx_server:
            print("[-] Could not find a mail server for this domain. Aborting.")
            return
        print(f"[+] Using mail server: {mx_server}\n")

        print("[*] Checking whether domain is catch-all...")
        if check_catch_all(mx_server, domain):
            print("[!] This domain accepts ALL addresses (catch-all). SMTP verification")
            print("    won't reliably tell real addresses from fake ones for this domain.")
            print("    Showing the most statistically likely pattern as a best guess:\n")

            results = {}
            for name in names:
                first, last = split_name(name)
                candidates = generate_candidates(first, last, domain)
                results[name] = candidates[0] if candidates else None

            print_summary(results)
            return

        print(f"[*] Processing {len(names)} names...\n")
        results = {}

        for i, name in enumerate(names, 1):
            print(f"[{i}/{len(names)}] Testing '{name}'...")
            email = process_single_name(name, domain, mx_server, verbose=False)
            results[name] = email

            if email:
                print(f"  ✅ Found: {email}")
            else:
                print(f"  ❌ No match found")
            print()

        print_summary(results)
        save_results_to_file(results, domain)
        return

    # Interactive mode
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    EMAIL FINDER TOOL                        ║
║                    Version 1.0.0                            ║
╚══════════════════════════════════════════════════════════════╝
""")

    try:
        print("Select mode:")
        print("  1. Single name lookup")
        print("  2. Batch mode (from text file)")
        print("  3. Exit")

        choice = input_simple("\nEnter choice (1-3): ").strip()

        if choice == '1':
            interactive_mode()
        elif choice == '2':
            batch_mode()
        elif choice == '3':
            print("\nExiting...")
            return
        else:
            print("[-] Invalid choice. Please select 1, 2, or 3.")
            main()
    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user.")
        print("[!] Exiting gracefully...")
        sys.exit(0)
    except EOFError:
        print("\n\n[!] Input stream closed. Exiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()

