from tibanna.stepfunction_cost_updater import StepFunctionCostUpdater

def test_StepFunctionCostUpdater():
    sf = StepFunctionCostUpdater()
    assert sf.sfn_start_lambda == 'Wait'
    assert sf.definition['States'] == sf.sfn_state_defs
    assert sf.definition['StartAt'] == 'Wait'
    assert 'Wait' in sf.sfn_state_defs
    assert 'UpdateCostAwsem' in sf.sfn_state_defs
    assert 'UpdateCostDone' in sf.sfn_state_defs
    assert 'Done' in sf.sfn_state_defs
    correct_lambda_name = 'arn:aws:lambda:us-east-1:%s:function:update_cost_awsem' % sf.aws_acc
    assert sf.sfn_state_defs['UpdateCostAwsem']['Resource'] == correct_lambda_name
    # try changing dev suffix
    sf.dev_suffix = 'dev'
    correct_lambda_name = 'arn:aws:lambda:us-east-1:%s:function:update_cost_awsem_dev' % sf.aws_acc
    assert sf.sfn_state_defs['UpdateCostAwsem']['Resource'] == correct_lambda_name
