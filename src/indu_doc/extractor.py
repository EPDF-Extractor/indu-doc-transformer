import os
import json

if __name__ == "__main__":
    # args are paths to one or more pdf files
    import sys
    from tqdm import tqdm

    pdf_files = sys.argv[1:]
    if not pdf_files:
        print("No PDF files provided.")
    else:
        for pdf_file in pdf_files:
            for i in tqdm(range(10), desc=f"Processing {pdf_file}"):
                pass

            print("Output file: out_" + pdf_file.split(".")[0] + ".aml")
