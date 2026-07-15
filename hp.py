import requests
import json
import regex
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

'''
Demo to download updated 'Hospitals' themed datasets from CMS with cleaned header names.  

Downloaded files are named with the dataset id to avoid collisions.

'downloaded.log' tracks the downloaded files and their details.  'failed.log' tracks files failures.

For production usage consider additional error handling, logging, configuration, typing.... 
'''

data_dir = 'hospital_data'
download_log = 'downloaded.log'
failed_log = 'failed.log'

def get_dataset_items(theme):
    url = 'https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items'

    resp = requests.get(url, timeout=10)
    datasets = json.loads(resp.content)
    hospital_datasets = {
        d['identifier']:{'title': d['title'], 'modified': d['modified'], 'url': d['distribution'][0]['downloadURL']}
        for d in datasets if theme in d['theme']}

    assert len(hospital_datasets) > 0 #should always find some

    return hospital_datasets

def get_dowloaded_items():
    dl_status = {}
    try:
        with open(Path(data_dir, download_log), 'r') as f:
            dl_status = json.load(f)
    except Exception as e:
        pass
    return dl_status

def generate_download_list(latest_datasets, existing_datasets):
    if existing_datasets:
        dl = {k:v for k,v in latest_datasets.items() if v['modified'] > existing_datasets.get(k, {'modified':'1900-01-01'})['modified']}
    else:
        dl = latest_datasets

    return dl

def download(item):
    filename, details = item
    res = (False, filename, details)
    try:
        resp = requests.get(details['url'], timeout=10)

        if resp.ok:
            lines = resp.text.splitlines()
            snake_hdr = regex.sub(r'[^a-zA-Z0-9_,]+', '_', lines[0].lower())
            lines[0] = regex.sub(r'_(?=,)|^_|(?<=,)_|_$', '', snake_hdr)  # also remove underscore at start/end of column name

            with open(Path(data_dir, filename + '.csv'), 'w') as f:
                f.write('\n'.join(lines))

            res = (True, filename, details)

    except Exception as e:
        pass

    return res

def parallel_download(download_list, workers=6):

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(download, download_list.items()))

    return results

def update_hospital_data():
    if not Path(data_dir).is_dir():
        Path(data_dir).mkdir()

    latest_datasets = get_dataset_items('Hospitals')
    print(f"Found {len(latest_datasets)} Hospital datasets")
    existing_datasets = get_dowloaded_items()
    download_list = generate_download_list(latest_datasets, existing_datasets)
    print(f"Downloading {len(download_list)} new or updated Hospital datasets")
    results = parallel_download(download_list)
    updated = {i[1]:i[2] for i in results if i[0]}
    failed = {i[1]:i[2] for i in results if not i[0]}
    print(f"{len(updated)} datasets downloaded")

    if len(failed) > 0:
        print(f"{len(failed)} datasets failed. Check log for details.")

    try:
        with open(Path(data_dir, download_log), 'w') as f:
            f.write(json.dumps(existing_datasets | updated, indent=4))
    except Exception as e:
        print('Failed to update download log')

    try:
        with open(Path(data_dir, failed_log), 'w') as f:
            f.write(json.dumps(failed, indent=4))
    except Exception as e:
        print('Failed to update failure log')


if __name__ == '__main__':
    update_hospital_data()