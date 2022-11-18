#!/usr/bin/python
import json
import time
import os
import logging
import boto3
import botocore
import re
from . import create_logger
from datetime import datetime, timedelta
from .utils import (
    does_key_exist,
    read_s3,
    put_object_s3
)
from .vars import (
    AWS_REGION,
    AWS_REGION_NAMES
)
from .exceptions import (
    PricingRetrievalException
)


logger = create_logger(__name__)


def get_cost(postrunjson, job_id):

    job = postrunjson.Job

    def reformat_time(t, delta):
        d = datetime.strptime(t, '%Y%m%d-%H:%M:%S-UTC') + timedelta(days=delta)
        return d.strftime("%Y-%m-%d")

    start_time = reformat_time(job.start_time, -1)  # give more room
    if(job.end_time != None):
        end_time = reformat_time(job.end_time, 1)
    else:
        end_time = datetime.utcnow() + timedelta(days=1) # give more room
        end_time = end_time.strftime("%Y-%m-%d")

    billing_args = {'Filter': {'Tags': {'Key': 'Name', 'Values': ['awsem-' + job_id]}},
                    'Granularity': 'DAILY',
                    'TimePeriod': {'Start': start_time,
                                    'End': end_time},
                    'Metrics': ['BlendedCost'],
                    }

    try:
        billingres = boto3.client('ce').get_cost_and_usage(**billing_args)
    except botocore.exceptions.ClientError as e:
        logger.warning("%s. Please try to deploy the latest version of Tibanna." % e)
        return 0.0

    cost = sum([float(_['Total']['BlendedCost']['Amount']) for _ in billingres['ResultsByTime']])
    return cost


def get_cost_estimate(postrunjson, ebs_root_type = "gp3", aws_price_overwrite = None):
    """
    aws_price_overwrite can be used to overwrite the prices obtained from AWS (e.g. ec2 spot price).
    This allows historical cost estimates. It is also used for testing. It is a dictionary with keys:
    ec2_spot_price, ec2_ondemand_price, ebs_root_storage_price, ebs_storage_price,
    ebs_iops_price (gp3, io1), ebs_io2_iops_prices, ebs_throughput_price
    """

    cfg = postrunjson.config
    job = postrunjson.Job
    estimated_cost = 0.0

    if(job.end_time == None):
        logger.warning("job.end_time not available. Cannot calculate estimated cost.")
        return 0.0, "NA"

    job_start = datetime.strptime(job.start_time, '%Y%m%d-%H:%M:%S-UTC')
    job_end = datetime.strptime(job.end_time, '%Y%m%d-%H:%M:%S-UTC')
    job_duration = (job_end - job_start).seconds / 3600.0 # in hours

    if(not job.instance_type):
        logger.warning("Instance type is not available for cost estimation. Please try to deploy the latest version of Tibanna.")
        return 0.0, "NA"

    try:
        pricing_client = boto3.client('pricing', region_name=AWS_REGION)

        # Get EC2 spot price
        if(cfg.spot_instance):
            if(cfg.spot_duration):
                raise PricingRetrievalException("Pricing with spot_duration is not supported")

            if(not job.instance_availablity_zone):
                raise PricingRetrievalException("Instance availability zone is not available. You might have to deploy a newer version of Tibanna.")
            
            ec2_client=boto3.client('ec2',region_name=AWS_REGION)
            prices=ec2_client.describe_spot_price_history(
                InstanceTypes=[job.instance_type],
                ProductDescriptions=['Linux/UNIX'],
                AvailabilityZone=job.instance_availablity_zone,
                MaxResults=1) # Most recent price is on top

            if(len(prices['SpotPriceHistory']) == 0):
                raise PricingRetrievalException("Spot price could not be retrieved")

            ec2_spot_price = (float)(prices['SpotPriceHistory'][0]['SpotPrice'])

            if((aws_price_overwrite is not None) and 'ec2_spot_price' in aws_price_overwrite):
                ec2_spot_price = aws_price_overwrite['ec2_spot_price']

            estimated_cost = estimated_cost + ec2_spot_price * job_duration

        else: # EC2 onDemand Prices

            prices = pricing_client.get_products(ServiceCode='AmazonEC2', Filters=[
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'instanceType',
                    'Value': job.instance_type
                },
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'operatingSystem',
                    'Value': 'Linux'
                },
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'location',
                    'Value': AWS_REGION_NAMES[AWS_REGION]
                },
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'preInstalledSw',
                    'Value': 'NA'
                },
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'capacitystatus',
                    'Value': 'used'
                },
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'tenancy',
                    'Value': 'Shared'
                },
            ])
            price_list = prices["PriceList"]

            if(not prices["PriceList"] or len(price_list) == 0):
                raise PricingRetrievalException("We could not retrieve EC2 prices from Amazon")

            if(len(price_list) > 1):
                raise PricingRetrievalException("EC2 prices are ambiguous")

            price_item = json.loads(price_list[0])
            terms = price_item["terms"]
            term = list(terms["OnDemand"].values())[0]
            price_dimension = list(term["priceDimensions"].values())[0]
            ec2_ondemand_price = (float)(price_dimension['pricePerUnit']["USD"])


            if((aws_price_overwrite is not None) and 'ec2_ondemand_price' in aws_price_overwrite):
                ec2_ondemand_price = aws_price_overwrite['ec2_ondemand_price']

            estimated_cost = estimated_cost + ec2_ondemand_price * job_duration


        # Get EBS pricing

        prices = pricing_client.get_products(ServiceCode='AmazonEC2', Filters=[
            {
                'Type': 'TERM_MATCH',
                'Field': 'location',
                'Value': AWS_REGION_NAMES[AWS_REGION]
            },
            {
                'Field': 'volumeApiName',
                'Type': 'TERM_MATCH',
                'Value': ebs_root_type,
            },
            {
                'Field': 'productFamily',
                'Type': 'TERM_MATCH',
                'Value': 'Storage',
            },
        ])
        price_list = prices["PriceList"]

        if(not prices["PriceList"] or len(price_list) == 0):
            raise PricingRetrievalException("We could not retrieve EBS prices from Amazon")

        if(len(price_list) > 1):
            raise PricingRetrievalException("EBS prices are ambiguous")

        price_item = json.loads(price_list[0])
        terms = price_item["terms"]
        term = list(terms["OnDemand"].values())[0]
        price_dimension = list(term["priceDimensions"].values())[0]
        ebs_root_storage_price = (float)(price_dimension['pricePerUnit']["USD"])

        if((aws_price_overwrite is not None) and 'ebs_root_storage_price' in aws_price_overwrite):
            ebs_root_storage_price = aws_price_overwrite['ebs_root_storage_price']

        # add root EBS costs
        root_ebs_cost = ebs_root_storage_price * cfg.root_ebs_size * job_duration / (24.0*30.0)
        estimated_cost = estimated_cost + root_ebs_cost

        # add additional EBS costs
        if(cfg.ebs_type == "gp3"):
            ebs_storage_cost = ebs_root_storage_price * cfg.ebs_size * job_duration / (24.0*30.0)
            estimated_cost = estimated_cost + ebs_storage_cost

            # Add throughput
            if(cfg.ebs_throughput):
                prices = pricing_client.get_products(ServiceCode='AmazonEC2', Filters=[
                    {
                        'Type': 'TERM_MATCH',
                        'Field': 'location',
                        'Value': AWS_REGION_NAMES[AWS_REGION]
                    },
                    {
                        'Field': 'volumeApiName',
                        'Type': 'TERM_MATCH',
                        'Value': cfg.ebs_type,
                    },
                    {
                        'Field': 'productFamily',
                        'Type': 'TERM_MATCH',
                        'Value': 'Provisioned Throughput',
                    },
                ])
                price_list = prices["PriceList"]

                if(not prices["PriceList"] or len(price_list) == 0):
                    raise PricingRetrievalException("We could not retrieve EBS throughput prices from Amazon")

                if(len(price_list) > 1):
                    raise PricingRetrievalException("EBS throughput prices are ambiguous")

                price_item = json.loads(price_list[0])
                terms = price_item["terms"]
                term = list(terms["OnDemand"].values())[0]
                price_dimension = list(term["priceDimensions"].values())[0]
                ebs_throughput_price = (float)(price_dimension['pricePerUnit']["USD"])/1000 # unit: mbps

                if((aws_price_overwrite is not None) and 'ebs_throughput_price' in aws_price_overwrite):
                    ebs_throughput_price = aws_price_overwrite['ebs_throughput_price']

                free_tier = 125
                ebs_throughput_cost = ebs_throughput_price * max(cfg.ebs_throughput - free_tier, 0) * job_duration / (24.0*30.0)
                estimated_cost = estimated_cost + ebs_throughput_cost

        else:
            prices = pricing_client.get_products(ServiceCode='AmazonEC2', Filters=[
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'location',
                    'Value': AWS_REGION_NAMES[AWS_REGION]
                },
                {
                    'Field': 'volumeApiName',
                    'Type': 'TERM_MATCH',
                    'Value': cfg.ebs_type,
                },
                {
                    'Field': 'productFamily',
                    'Type': 'TERM_MATCH',
                    'Value': 'Storage',
                },
            ])
            price_list = prices["PriceList"]

            if(not prices["PriceList"] or len(price_list) == 0):
                raise PricingRetrievalException("We could not retrieve EBS prices from Amazon")

            if(len(price_list) > 1):
                raise PricingRetrievalException("EBS prices are ambiguous")

            price_item = json.loads(price_list[0])
            terms = price_item["terms"]
            term = list(terms["OnDemand"].values())[0]
            price_dimension = list(term["priceDimensions"].values())[0]
            ebs_storage_price = (float)(price_dimension['pricePerUnit']["USD"])

            if((aws_price_overwrite is not None) and 'ebs_storage_price' in aws_price_overwrite):
                ebs_storage_price = aws_price_overwrite['ebs_storage_price']

            add_ebs_cost = ebs_storage_price * cfg.ebs_size * job_duration / (24.0*30.0)
            estimated_cost = estimated_cost + add_ebs_cost

        ## IOPS PRICING
        # Add IOPS prices for io1 or gp3
        if( (cfg.ebs_type == "io1" or cfg.ebs_type == "gp3") and cfg.ebs_iops):
            prices = pricing_client.get_products(ServiceCode='AmazonEC2', Filters=[
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'location',
                    'Value': AWS_REGION_NAMES[AWS_REGION]
                },
                {
                    'Field': 'volumeApiName',
                    'Type': 'TERM_MATCH',
                    'Value': cfg.ebs_type,
                },
                {
                    'Field': 'productFamily',
                    'Type': 'TERM_MATCH',
                    'Value': 'System Operation',
                },
            ])
            price_list = prices["PriceList"]

            if(not prices["PriceList"] or len(price_list) == 0):
                raise PricingRetrievalException("We could not retrieve EBS prices from Amazon")
            if(len(price_list) > 1):
                raise PricingRetrievalException("EBS prices are ambiguous")

            price_item = json.loads(price_list[0])
            terms = price_item["terms"]
            term = list(terms["OnDemand"].values())[0]
            price_dimension = list(term["priceDimensions"].values())[0]
            ebs_iops_price = (float)(price_dimension['pricePerUnit']["USD"])

            if((aws_price_overwrite is not None) and 'ebs_iops_price' in aws_price_overwrite):
                ebs_iops_price = aws_price_overwrite['ebs_iops_price']

            if cfg.ebs_type == "gp3":
                free_tier = 3000
                ebs_iops_cost = ebs_iops_price * max(cfg.ebs_iops - free_tier, 0) * job_duration / (24.0*30.0)
            else:
                ebs_iops_cost = ebs_iops_price * cfg.ebs_iops * job_duration / (24.0*30.0)

            estimated_cost = estimated_cost + ebs_iops_cost

        elif (cfg.ebs_type == "io2" and cfg.ebs_iops):
            prices = pricing_client.get_products(ServiceCode='AmazonEC2', Filters=[
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'location',
                    'Value': AWS_REGION_NAMES[AWS_REGION]
                },
                {
                    'Field': 'volumeApiName',
                    'Type': 'TERM_MATCH',
                    'Value': cfg.ebs_type,
                },
                {
                    'Field': 'productFamily',
                    'Type': 'TERM_MATCH',
                    'Value': 'System Operation',
                },
            ])
            price_list = prices["PriceList"]

            if(len(price_list) != 3):
                raise PricingRetrievalException("EBS prices for io2 are incomplete")

            ebs_io2_iops_prices = []
            for price_entry in price_list:
                price_item = json.loads(price_entry)
                terms = price_item["terms"]
                term = list(terms["OnDemand"].values())[0]
                price_dimension = list(term["priceDimensions"].values())[0]
                ebs_iops_price = (float)(price_dimension['pricePerUnit']["USD"])
                ebs_io2_iops_prices.append(ebs_iops_price)
            ebs_io2_iops_prices.sort(reverse=True)

            if((aws_price_overwrite is not None) and 'ebs_io2_iops_prices' in aws_price_overwrite):
                ebs_io2_iops_prices = aws_price_overwrite['ebs_io2_iops_prices']

            # Pricing tiers are currently hardcoded. There wasn't a simple way to extract them from the pricing information
            tier0 = 32000
            tier1 = 64000

            ebs_iops_cost = (
                ebs_io2_iops_prices[0] * min(cfg.ebs_iops, tier0) + # Portion below 32000 IOPS
                ebs_io2_iops_prices[1] * min(max(cfg.ebs_iops - tier0, 0), tier1 - tier0) + # Portion between 32001 and 64000 IOPS
                ebs_io2_iops_prices[2] * max(cfg.ebs_iops - tier1, 0) # Portion above 64000 IOPS
                ) * job_duration / (24.0*30.0)
            estimated_cost = estimated_cost + ebs_iops_cost

        time_since_run = (datetime.utcnow() - job_end).total_seconds() / (3600 * 24) # days
        estimation_type = "retrospective estimate" if time_since_run > 10 else "immediate estimate"

        return estimated_cost, estimation_type

    except botocore.exceptions.ClientError as e:
        logger.warning("Cost estimation error: %s. Please try to deploy the latest version of Tibanna." % e)
        return 0.0, "NA"
    except PricingRetrievalException as e:
        logger.warning("Cost estimation error: %s" % e)
        return 0.0, "NA"
    except Exception as e:
        logger.warning("Cost estimation error: %s" % e)
        return 0.0, "NA"


def get_cost_estimate_from_tsv(log_bucket, job_id):

    s3_key = os.path.join(job_id + '.metrics/', 'metrics_report.tsv')
    cost_estimate = 0.0
    cost_estimate_type = "NA"

    if(does_key_exist(log_bucket, s3_key) == False):
        return cost_estimate, cost_estimate_type

    try:
        read_file = read_s3(log_bucket, s3_key)
        for row in read_file.splitlines():
            line = row.split("\t")
            if(line[0] == "Estimated_Cost"):
                cost_estimate = float(line[1])
            if(line[0] == "Estimated_Cost_Type"):
                cost_estimate_type = line[1]
    except Exception as e:
        logger.warning("Could not get cost estimate from tsv: %s" % e)
        pass

    return cost_estimate, cost_estimate_type


def update_cost_estimate_in_tsv(log_bucket, job_id, cost_estimate, cost_estimate_type, encryption=False, kms_key_id=None):

    s3_key = os.path.join(job_id + '.metrics/', 'metrics_report.tsv')

    if(does_key_exist(log_bucket, s3_key) == False):
        return

    # reading from metrics_report.tsv
    read_file = read_s3(log_bucket, s3_key)

    # get the current estimate type in the file
    for row in read_file.splitlines():
        line = row.split("\t")
        if(line[0] == "Estimated_Cost_Type"):
            current_cost_estimate_type = line[1]

    if(cost_estimate_type=="retrospective estimate" and (current_cost_estimate_type=="immediate estimate" or current_cost_estimate_type=="actual cost") ):
        logger.warning("There already is a probably more accurate estimate in the tsv. Not updating.")
        return

    write_file = ""
    for row in read_file.splitlines():
        # Remove Estimated_Cost and Estimated_Cost_Type from file, since we want to update it
        if("Estimated_Cost" in row.split("\t") or "Estimated_Cost_Type" in row.split("\t")):
            continue
        if("Cost" in row.split("\t") and cost_estimate_type=="actual cost"):
            continue
        write_file = write_file + row + '\n'

    if(cost_estimate_type=="actual cost"):
        write_file = write_file + 'Cost\t' + str(cost_estimate) + '\n'
    write_file = write_file + 'Estimated_Cost\t' + str(cost_estimate) + '\n'
    write_file = write_file + 'Estimated_Cost_Type\t' + cost_estimate_type + '\n'
    put_object_s3(content=write_file, key=s3_key, bucket=log_bucket,
                  encrypt_s3_upload=encryption, kms_key_id=kms_key_id)


def update_cost_in_tsv(log_bucket, job_id, cost,
                       encryption=False, kms_key_id=None):

    s3_key = os.path.join(job_id + '.metrics/', 'metrics_report.tsv')

    if(does_key_exist(log_bucket, s3_key) == False):
        return

    # reading from metrics_report.tsv
    read_file = read_s3(log_bucket, s3_key)

    write_file = ""
    for row in read_file.splitlines():
        # Remove Cost from file, since we want to update it
        if("Cost" not in row.split("\t")):
            write_file = write_file + row + '\n'

    write_file = write_file + 'Cost\t' + str(cost) + '\n'
    put_object_s3(content=write_file, key=s3_key, bucket=log_bucket,
                  encrypt_s3_upload=encryption, kms_key_id=kms_key_id)
