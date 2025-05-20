import argparse
import re
import itertools
import subprocess
import random
import string
import os
import sys
import tldextract
import threading
import queue
import pyfiglet

print(pyfiglet.figlet_format("Astro DNS", font="starwars"))

resolvers_file = "resolvers.txt" # Enter resolvers file path. if not provided astro will use trickest resolver by default.
notify_provider_config="" # Enter notify provider config path
wordlist_url = "https://raw.githubusercontent.com/n0kovo/n0kovo_subdomains/refs/heads/main/n0kovo_subdomains_small.txt" # Provide Wordlist file

if not os.path.exists(notify_provider_config):
    print("❌ Notify provider file not found or not updated in the script")
    sys.exit(1) 

if not os.path.exists(resolvers_file):
    print("❌ Resolvers file not found. Downloading resolvers")
    resolver__download_command = ["wget", 'https://raw.githubusercontent.com/trickest/resolvers/refs/heads/main/resolvers.txt', "-O", 'resolvers.txt']
    subprocess.run(resolver__download_command,stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def random_filename(extension="txt"):
    name = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{name}.{extension}"

################################################
# Below section code looks for places where bruteforcing can be done based below rules. 
# for eg: black.api.example.com -> generate variations:
# (*.api.example.com, black.*.example.com, black-*.api.example.com,*-black.api.example.com, black.*-api.example.com, black.api-*.example.com)
################################################

def generate_variants(url):
    extracted = tldextract.extract(url)
    main_domain = extracted.domain
    tld = extracted.suffix
    subdomains = extracted.subdomain.split('.') if extracted.subdomain else []

    if not main_domain or not tld:
        return [url]

    variants = set()

    # Rule 1:
    if subdomains:
        temp_subdomains = subdomains[:]
        temp_subdomains[0] = '*' 
        variants.add('.'.join(temp_subdomains + [main_domain, tld]))

        if '-' in subdomains[0]:
            temp_subdomains[0] = '*-' + subdomains[0].split('-', 1)[1]
            variants.add('.'.join(temp_subdomains + [main_domain, tld]))

    # Rule 2:
    for i in range(1, len(subdomains)):
        temp_subdomains = subdomains[:]
        temp_subdomains[i] = '*'
        variants.add('.'.join(temp_subdomains + [main_domain, tld]))

    # Rule 3:
    for i, sub in enumerate(subdomains):
        hyphen_parts = sub.split('-')
        
        if len(hyphen_parts) > 1:
            for j in range(1, len(hyphen_parts)):
                temp_subdomains = subdomains[:]
                temp_hyphen_parts = hyphen_parts[:]
                temp_hyphen_parts[j] = '*' 
                temp_subdomains[i] = '-'.join(temp_hyphen_parts)
                variants.add('.'.join(temp_subdomains + [main_domain, tld]))

    # Rule 4:
    if len(subdomains) >= 2:
        first, second = subdomains[:2]

        variants.add(f'*.{second}.{main_domain}.{tld}')
        variants.add(f'{first}-*.{second}.{main_domain}.{tld}')

        if '-' in second:
            pre, post = second.split('-', 1)
            variants.add(f'{first}.*-{post}.{main_domain}.{tld}')
            variants.add(f'{first}.{pre}-*.{main_domain}.{tld}')

    #Rule 5:   
    for i, sub in enumerate(subdomains):
        # *-sub
        temp_subdomains_star_prefix = subdomains[:]
        temp_subdomains_star_prefix[i] = f'*-{sub}'
        variants.add('.'.join(temp_subdomains_star_prefix + [main_domain, tld]))

        # sub-*
        temp_subdomains_star_suffix = subdomains[:]
        temp_subdomains_star_suffix[i] = f'{sub}-*'
        variants.add('.'.join(temp_subdomains_star_suffix + [main_domain, tld]))
 
    return sorted(variants)

def feeder_process(input_file, output_file):
    with open(input_file, 'r') as file:
        lines = file.readlines()
    
    all_variants = set()
    for line in lines:
        sanitized_variants = generate_variants(line.strip())
        all_variants.update(sanitized_variants)

    # Save output to a file
    with open(output_file, 'w') as file:
        file.write("\n".join(sorted(all_variants)))

    print(f"\nfeeder file saved!!🚀")

parser = argparse.ArgumentParser(description="AstroDNS on work")
parser.add_argument("input_file", type=str, help="Parse known subdomain file for eg: python3 astrodns.py list_of_known_subdomains.txt (wihtout any protocol or ports)")
args = parser.parse_args()
feeder_file = args.input_file + '_' + random_filename() + ".feeder"
print("\nGenerating feeder")
feeder_process(args.input_file, feeder_file)

#################################################################
# Section -> Download Wordlist

print (f"\nGetting Started with resolving...🚨")
randomfilename =random_filename()
temp_filename = randomfilename + ".part"
final_filename = randomfilename

command = ["wget", wordlist_url, "-O", temp_filename]
result = subprocess.run(command,stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if result.returncode == 0:
    os.rename(temp_filename, final_filename)
else:
    print("Download failed!")
    os.remove(temp_filename)

#######################################################################################################
# Section -> Generate 3 letter combos and concate them to the wordlist

def genereate_3_letter_combo():
    return ["".join(combo) for combo in itertools.product(string.ascii_lowercase, repeat=3)]   # Generates all possible 3 letter combination (this covers api,dev,stg,uat,pip and etc)

three_letter_combos = genereate_3_letter_combo()  # Add comment in below 3 lines if you dont need to add all possible 3 letter combo.
with open(final_filename,"a") as out_file: 
    out_file.write("\n".join(three_letter_combos) + "\n")

########################################################################################################
# Section -> Handles notification via notify. Only notifies if domain is new by checking if domain is present in input file 

def normalize_domain(url):
    return url.lower().replace("https://", "").replace("http://", "").strip("/")

def find_new_entries(file_a):
    if not os.path.exists(file_a) or not os.path.exists(args.input_file):
        return

    with open(args.input_file, "r") as fb:
        set_b = {normalize_domain(line.strip()) for line in fb}

    new_entries = []

    with open(file_a, "r") as fa:
        for line in fa:
            raw_line = line.strip()
            norm_line = normalize_domain(raw_line)
            if norm_line not in set_b:
                new_entries.append(raw_line)

    if new_entries:
        notify_file = random_filename() + ".notify"
        with open(notify_file, "w") as fout:
            fout.write("\n".join(new_entries) + "\n")

        notify_command = ['notify', '-silent', '-provider-config', notify_provider_config, '-data', notify_file]
        subprocess.run(notify_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(notify_file)

#######################################################################################################
# Section -> Handles filtering on output generated by PugDNS. Removes out of scope domains

def normalize_tld(ref):
    return ref.strip().lower()

def filter_and_replace_input(file_path, reference_list):
    allowed_main_domains = {
        tldextract.extract(normalize_tld(ref)).domain
        for ref in reference_list
    }
    with open(file_path, "r") as f:
        lines = [normalize_tld(line) for line in f]
    filtered_lines = [
        line for line in lines
        if tldextract.extract(line).domain in allowed_main_domains
    ]
    with open(file_path, "w") as f:
        f.write("\n".join(filtered_lines) + "\n")

#######################################################################################################
# Section -> Handles Queues for httpx process. Only 1 httpx process runs at a time and rest httpx process waits in queue.

cleanup_queue = queue.Queue()
def cleanup_worker():
    global cleanup_queue
    while True:
        cleaning_command, final_output_txt = cleanup_queue.get()
        if cleaning_command is None:
            break

        proc = subprocess.Popen(
            cleaning_command, shell=True, executable="/bin/bash",
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        proc.wait()
        if os.path.exists(final_output_txt):
            find_new_entries(final_output_txt)

        cleanup_queue.task_done()

cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
cleanup_thread.start()


#######################################################################################################
# Section -> Responsible for starting PureDNS.
# Domains are processed in batches. So that PureDNS doesn't eats all your Memory and to avoid crashes.
# Script works perfectly at batch size of 4 (6Gb Ram, 4 cpu), You can edit this batch size according to your configuration.
# This batch is not thread keep it low according to your size of wordlist. eg: 4 domains x Number of words in your wordslists. this amount of possible subdomain will be resolved by PureDNS.
# If scrtipt crashes in between then considered reducing batch size. (Manual Clean up of PureDNS and httpx process is required if script crashes in between)
######################################################################################################

def process_domains(domains, wordlist_file):
    if not os.path.exists(wordlist_file):
        print(f"Wordlist file {wordlist_file} not found!")
        return
    with open(wordlist_file, "r") as file:
        words = file.read().splitlines()

    generated_domains = []
    for domain in domains:
        generated_domains.extend([domain.replace("*", word) for word in words])

    output_file = random_filename()
    with open(output_file, "w") as out_file:
        out_file.write("\n".join(generated_domains))

    output_file_pugdns = "result_" + random_filename() + ".output"
    puredns_command = ["puredns", "resolve", output_file, "-r", resolvers_file, "--bin", "massdns", "--write", output_file_pugdns]

    print(f"\n🚀......Starting PureDNS......... 🚀")
    with open("/dev/null", "w") as fnull:
        subprocess.run(puredns_command)
    print(f"\n❇️ .....PureDNS Completed.......")  

    filter_output_txt = "filter_" + random_filename() + ".filter" 
    final_output_txt = "result_" + random_filename() + ".final"
    
    if os.path.exists(output_file):
        os.remove(output_file)
    
    filter_command = f"""
    cat {output_file_pugdns} | sort -fu > {filter_output_txt}
    """
    subprocess.run(filter_command,shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(output_file_pugdns):
        os.remove(output_file_pugdns)
        
    with open(args.input_file, "r") as f:
        reference_list = f.read().splitlines()
    filter_and_replace_input(filter_output_txt, reference_list)
    cleaning_command = f"""
    cat {filter_output_txt}| sort -fu|\
    httpx -t 100 -p 80,443,8080,8443,8000,8888,3000,3001,5000,8085,5173,8081,9000,9001,10000,81,7777,9999,8089,27017,9200,5601,15672,6379,10250,10255,6443,2375,2376 -o {final_output_txt}
    """
    cleanup_queue.put((cleaning_command, final_output_txt))

def process_file_1(file_path, wordlist_file, batch_size=4):                   # Edit batch size here. Default is 4.
    """Read domains from file and process them in batches of 10."""
    if not os.path.exists(file_path):
        print(f"Input file {file_path} not found!")
        return

    with open(file_path, "r") as file:
        domains = [line.strip() for line in file if line.strip()]

    for i in range(0, len(domains), batch_size):
        batch = domains[i:i + batch_size]
        process_domains(batch, wordlist_file)

        
process_file_1(feeder_file, final_filename)

#######################################################################################################
# Section -> Waits for all the httpx process to be completed
print("⏳ Waiting for all realtime httpx processes to be completed...")
cleanup_queue.join()

#######################################################################################################
# Section -> Performs final cleanUP and saves the final output

print("\n🗑️ Preparing Clean UP....")
os.remove(final_filename)

combine_file= args.input_file + ".resolved"

subprocess.run(f"cat *.final | sort -u > {combine_file}", shell=True, executable="/bin/bash")
subprocess.run("rm *.final", shell=True, executable="/bin/bash")
subprocess.run("rm *.filter", shell=True, executable="/bin/bash")

print(f"\n🎉 All astro process completed and output save to {combine_file}")

