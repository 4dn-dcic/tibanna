## test samples
```
invoke run_workflow --input-json='./test_json/hic_parta_input2.json' # tiny files
invoke run_workflow --input-json='./test_json/hic_parta_input3.json' # Koray's MySeq files (20170411)
invoke run_workflow --input-json='./test_json/md5_input.json' # md5, tiny file
invoke run_workflow --input-json='./test_json/fastqc_input.json' # fastqc, tiny file
# (the three workflows can be run simultaneously, all using different input files))
```

## major changes
* processed file metadata (first post at export_files_sbg)
* output file-type dependent export (for processed file metadata, the file name is set before export file_uuid/file_accession.
* It's currently using step function run_sbg_workflow_2-3 - with shorter check intervals.

## to do
* add file extension to the processed file name (file_uuid/file_accession + file_extension)
* check_export branching should be based on output file type not app name.
* add pairsqc_updater or have a generic function that handles both fastqc and pairsqc (and bamqc)
    * we need to decide where to link the pairsqc - to fastq files (input) or pairs file (output)? 
* currently output file information is in three places: processed_file (pf_meta), ff_meta.output_files, sbg.export_report (this causes a lot of confusing)
* more tests & code clean-up
* SBG task ID missing from the ff_meta (not important)
* metadata/fourfront-independent path (for general pipelines (e.g. GATK) without having to update all the metadata from fourfront) - this would be useful if we want to make Tibanna public.

## I made the following patches to testportal

```
# Make sure you have the following metadata objects on test portal.
# Go to Submit4dn branch patch.
cd Submit4dn

## patch workflows to have 'argument' field.
# hicparta
python tests/post.py -k ~/.4dn_fourfront_key.json -p Data_Files/workflows/steps5b.json -s analysis_step
python tests/patch.py -k ~/.4dn_fourfront_key.json -p Data_Files/workflows/workflow5b.json -u 02d636b9-d82d-4da9-950c-2ca994a0943e

# md5
python tests/patch.py -k ~/.4dn_fourfront_key.json -p Data_Files/workflows/workflow6.json -u d3f25cd3-e726-4b3c-a022-48f844474b41

# fastqc
python tests/patch.py -k ~/.4dn_fourfront_key.json -p Data_Files/workflows/workflow7.json -u 2324ad76-ff37-4157-8bcc-3ce72b7dace9


# To post tiny test sample fastq data
python tests/post.py -k ~/.4dn_fourfront_key.json -p Data_Files/sample_fastq/sample1.json -s file_fastq
python tests/post.py -k ~/.4dn_fourfront_key.json -p Data_Files/sample_fastq/sample2.json -s file_fastq
python tests/post.py -k ~/.4dn_fourfront_key.json -p Data_Files/sample_fastq/sample3.json -s file_fastq
python tests/post.py -k ~/.4dn_fourfront_key.json -p Data_Files/sample_fastq/sample4.json -s file_fastq

# chrom.size file (This is for an upcoming hic_processing_parta and _partb)
python tests/post.py -k ~/.4dn_fourfront_key.json -p Data_Files/reference_files/file_reference3.json -s file_reference
```
