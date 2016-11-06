import requests
import json

base_url = "https://api.sbgenomics.com/v2/"

def run_task(token):
    url = base_url + "tasks"

    headers = {'X-SBG-Auth-Token': token,
               'Content-Type': 'application/json'}

    #payload
    data = {"description": "GITAR workflow - api test 1",
            "name": "GITAR workflow - api test 1",
            "app": "gaurav/4dn/gitar-workflow",
            "project": "gaurav/4dn",
            "inputs": {
                "input_fastq1": {
                    "class": "File",
                    "path": "575099c9e4b05276abbf34d7",
                    "name": "GM12878_SRR1658581_1pc_1_R1.fastq"
                },
                "input_fastq2": {
                    "class": "File",
                    "path": "575099c6e4b05276abbf34d4",
                    "name": "GM12878_SRR1658581_1pc_1_R2.fastq"
                },
                "output_prefix": "api_test",
                "output_dir": "api_test",
                "chromosome": ['21','22'],
                "contact_matrix_binsize": 50000
            }
           }
    resp = requests.post(url, headers=headers, data=json.dumps(data))
    print(resp.json())

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fun with 7Bridges")
    parser.add_argument('--token', help='your 7Bridges api access token')
    args = parser.parse_args()
    run_task(args.token)
