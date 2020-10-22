
def test_add_download_cmd():
    fo = open('tmp','w')
    from .awsf import aws_decode_run_json  as a
    a.add_download_cmd('buck', 'fil', 'targ', '--profile user1', fo, '')
    a.add_download_cmd('buck', 'fil', 'targ', '--profile user1', fo, 'gz')
    a.add_download_cmd('buck', 'fil2', 'targ2', '--profile user1', fo, 'bz2')
    fo.close()
    f = open('tmp', 'r')
    s = f.readlines()
    assert s == "if [[ -z $(aws s3 ls s3://buck/fil/) ]]; then aws s3 cp s3://buck/fil targ --profile user1;  else aws s3 cp --recursive s3://buck/fil targ --profile user1;  fi\n" + \
                "if [[ -z $(aws s3 ls s3://buck/fil/) ]]; then aws s3 cp s3://buck/fil targ --profile user1; gunzip targ; else aws s3 cp --recursive s3://buck/fil targ --profile user1; for f in `find targ -type f`; do if [[ $f =~ \.gz$ ]]; then gunzip $f; fi\n" + \
                "if [[ -z $(aws s3 ls s3://buck/fil2/) ]]; then aws s3 cp s3://buck/fil2 targ2 --profile user1; bzip2 -d targ2; else aws s3 cp --recursive s3://buck/fil2 targ2 --profile user1; for f in `find targ2 -type f`; do if [[ $f =~ \.bz2$ ]]; then bzip2 -d $f; fi\n"


if __name__ == '__main__':
    test_add_download_cmd()
