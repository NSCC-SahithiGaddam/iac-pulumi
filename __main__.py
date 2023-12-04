import pulumi
import pulumi_aws as aws
import pulumi_gcp as gcp
import json
import base64

zones = []
public_subnets = []
private_subnets = []

config = pulumi.Config()
DOMAIN = config.require('DOMAIN')
aws_region = config.require('AWS_REGION')
vpc_name = config.require('vpc_name')
igw_name = config.require('myigw_name')
webapp_port = config.require('webapp_port')
public_subnets_config = config.require_object('public_subnets_config')
private_subnets_config = config.require_object('private_subnets_config')
destination_route_cidr = config.require('destination_route_cidr')
ami_id = config.require('ami_id')
key_name = config.require('key_name')
http_cidr_blocks = config.require_object('http_cidr_blocks')
https_cidr_blocks = config.require_object('https_cidr_blocks')
webport_cidr_blocks = config.require_object('webport_cidr_blocks')
ssh_cidr_blocks = config.require_object('ssh_cidr_blocks')
instance_type = config.require('instance_type')
ENV_FILE_PATH = config.require('ENV_FILE_PATH')
DB_USER = config.require('DB_USER')
DB_PASSWORD = config.require('DB_PASSWORD')
DB_NAME = config.require('DB_NAME')
rds_instance_class = config.require('rds_instance_class')
rds_engine = config.require('rds_engine')
rds_engine_version = config.require('rds_engine_version')
rds_identifier = config.require('rds_identifier')
domain_name = config.require('domain_name')
MAIL_GUN_API_KEY = config.require('MAIL_GUN_API_KEY')
MAIL_GUN_DOMAIN = config.require('MAIL_GUN_DOMAIN')
gcs_bucket_name = config.require('gcs_bucket_name')

gcs_bucket = gcp.storage.Bucket("gcs_bucket",
    name= gcs_bucket_name,
    force_destroy=True,
    location="US",
    public_access_prevention='enforced',
    versioning=gcp.storage.BucketVersioningArgs(
        enabled=True
    ))

service_account = gcp.serviceaccount.Account("serviceAccount",
    account_id="dev-service-account-id",
    display_name="Service Account")

bucket_iam = gcp.storage.BucketIAMMember("bucketIAMMember",
    bucket=gcs_bucket.name,
    role="roles/storage.objectAdmin",
    member=pulumi.Output.concat("serviceAccount:", service_account.email))

access_key = gcp.serviceaccount.Key("access-key",
    service_account_id=service_account.name,
    public_key_type="TYPE_X509_PEM_FILE",
    private_key_type="TYPE_GOOGLE_CREDENTIALS_FILE")

create_vpc = aws.ec2.Vpc("main",
    cidr_block=config.require('cidr_block'),
    tags={
        "Name": vpc_name,
    })

create_igw = aws.ec2.InternetGateway("gw",
    vpc_id= create_vpc.id,
    tags={
        "Name": igw_name,
    })

availability_zones = aws.get_availability_zones(
    state="available"
)
availability_zone_count = len(availability_zones.names)
if availability_zone_count > 3:
    zones = availability_zones.names[:3]
else:
    zones = availability_zones.names

for i,zone in enumerate(zones):
    subnet = aws.ec2.Subnet(public_subnets_config[i]["name"],
    vpc_id=create_vpc.id,
    cidr_block=public_subnets_config[i]["cidr_block"],
    availability_zone = zone,
    tags={"Name": public_subnets_config[i]["name"]},
    )
    public_subnets.append(subnet.id)

for i,zone in enumerate(zones):
    subnet = aws.ec2.Subnet(private_subnets_config[i]["name"],
    vpc_id=create_vpc.id,
    cidr_block=private_subnets_config[i]["cidr_block"],
    availability_zone = zone,
    tags={"Name": private_subnets_config[i]["name"]},
    )
    private_subnets.append(subnet.id)

public_route_table = aws.ec2.RouteTable("public-route-table",
    vpc_id=create_vpc.id,
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block=destination_route_cidr,
            gateway_id=create_igw.id,
        )],
    tags={"Name": "public-route-table"},
)

private_route_table = aws.ec2.RouteTable("private-route-table",
    vpc_id=create_vpc.id,
    tags={"Name": "private-route-table"},
)

for n,subnet_id in enumerate(public_subnets):
    route_table_association = aws.ec2.RouteTableAssociation(f"myAssociation{n}",
    subnet_id=subnet_id,
    route_table_id=public_route_table.id,
    )
for n,subnet_id in enumerate(private_subnets, start=4):
    route_table_association = aws.ec2.RouteTableAssociation(f"myAssociation{n}",
    subnet_id=subnet_id,
    route_table_id=private_route_table.id,
    )
    
sns_topic = aws.sns.Topic("sns-topic",
    display_name = 'testSNS'
)
dynamodb_table = aws.dynamodb.Table("dynamodb-table",
    name = 'testtable',
    attributes=[
        aws.dynamodb.TableAttributeArgs(
            name="UserEmail",
            type="S",
        ),
        aws.dynamodb.TableAttributeArgs(
            name="Timestamp",
            type="S",
        )
    ],
    billing_mode="PROVISIONED",
    hash_key="UserEmail",
    range_key="Timestamp",
    read_capacity=20,
    tags={
        "Environment": "dev",
        "Name": "testtable",
    },
    write_capacity=20)

iam_for_lambda = aws.iam.Role("my-iam-role",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }""")

role_policy_attachment_dynamodb = aws.iam.RolePolicyAttachment("my-iam-role-policy",
    policy_arn="arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess",
    role=iam_for_lambda.name)
role_policy_attachment_lambda = aws.iam.RolePolicyAttachment('lambdaRolePolicy',
    role=iam_for_lambda.name,
    policy_arn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
)
testLambda = aws.lambda_.Function("testLambda",
    code=pulumi.FileArchive("./../serverless/Archive.zip"),
    role=iam_for_lambda.arn,
    handler="index.handler",
    runtime="nodejs20.x",
    timeout=60,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "GCS_BUCKET_NAME": gcs_bucket.name,
            "MAILGUN_API_KEY": MAIL_GUN_API_KEY,
            "MAILGUN_DOMAIN": MAIL_GUN_DOMAIN,
            "GCP_KEY": access_key.private_key,
            "DYNAMODB_NAME": dynamodb_table.name
        },
    ))

with_sns = aws.lambda_.Permission("withSns",
    action="lambda:InvokeFunction",
    function=testLambda.name,
    principal="sns.amazonaws.com",
    source_arn=sns_topic.arn)
lambda_sns_subscription = aws.sns.TopicSubscription("lambda-sns-subscription",
    topic=sns_topic.arn,
    protocol="lambda",
    endpoint=testLambda.arn)

loadbalancer_sg = aws.ec2.SecurityGroup("loadbalancer security group",
    description="Allow SSH, HTTP, HTTPS, WEBAPP_PORT",
    vpc_id=create_vpc.id,
    ingress=[
    aws.ec2.SecurityGroupIngressArgs(
        description="HTTPS",
        from_port=443,
        to_port=443,
        protocol="tcp",
        cidr_blocks=https_cidr_blocks,
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
    )],
    tags={
        "Name": "load balancer security group",
    })
application_sg = aws.ec2.SecurityGroup("application security group",
    description="Allow SSH, loadbalancer",
    vpc_id=create_vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        description="SSH",
        from_port=22,
        to_port=22,
        protocol="tcp",
        cidr_blocks=ssh_cidr_blocks,
    ),
    aws.ec2.SecurityGroupIngressArgs(
        description="WEBAPP_PORT",
        from_port=webapp_port,
        to_port=webapp_port,
        protocol="tcp",
        security_groups=[loadbalancer_sg.id],
    )],
    egress=[aws.ec2.SecurityGroupEgressArgs(
        from_port=0,
        to_port=0,
        protocol="-1",
        cidr_blocks=["0.0.0.0/0"],
    )],
    tags={
        "Name": "application security group",
    })

mariadb_parameter_group = aws.rds.ParameterGroup("mariadb-parameter-group",
    family="mariadb10.6",
    parameters=[
        aws.rds.ParameterGroupParameterArgs(
            name="max_user_connections",
            value=100,
            apply_method="pending-reboot"
        ),
    ])

database_sg = aws.ec2.SecurityGroup("database-security-group",
    description="Allow application to access database",
    vpc_id=create_vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        description="MySQL",
        from_port=3306,
        to_port=3306,
        protocol="tcp",
        security_groups=[application_sg.id],
    ),
    ],
    tags={
        "Name": "database security group",
    })

database_subnet_group = aws.rds.SubnetGroup("database-subnet-group",
    subnet_ids=private_subnets,
    tags={
        "Name": "database subnet group",
    })

database_instance = aws.rds.Instance("database instance",
    allocated_storage=20,
    db_name=DB_NAME,
    db_subnet_group_name=database_subnet_group.name,
    engine=rds_engine,
    engine_version=rds_engine_version,
    identifier=rds_identifier,
    instance_class=rds_instance_class,
    multi_az=False,
    publicly_accessible= False,
    parameter_group_name=mariadb_parameter_group.name,
    password=DB_PASSWORD,
    skip_final_snapshot=True,
    username=DB_USER,
    vpc_security_group_ids=[database_sg.id])
db_endpoint = database_instance.endpoint.apply(lambda endpoint: f'{endpoint}')

ec2_role = aws.iam.Role("ec2Role",
    name="ec2Role",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Sid": "",
            "Principal": {
                "Service": "ec2.amazonaws.com",
            },
        }],
    }),
    tags={
        "name": "cloudwatchRole",
    })

cloudWatchAgentPolicyAttachment = aws.iam.PolicyAttachment("cloudWatchAgentPolicyAttachment", 
    policy_arn= "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
    roles= [ec2_role.name],
)
SNSPolicyAttachment = aws.iam.PolicyAttachment("SNSPolicyAttachment", 
    policy_arn= "arn:aws:iam::aws:policy/AmazonSNSFullAccess",
    roles= [ec2_role.name],
)

instance_profile = aws.iam.InstanceProfile("instanceProfile", role=ec2_role.name)

my_instance_template = aws.ec2.LaunchTemplate("my_instance_template",
    name="demoTemplate",
    block_device_mappings=[aws.ec2.LaunchTemplateBlockDeviceMappingArgs(
        device_name="/dev/xvda",
        ebs=aws.ec2.LaunchTemplateBlockDeviceMappingEbsArgs(
            volume_size=20,
            volume_type="gp2",
            delete_on_termination=True,
        ),
    )],
    image_id=ami_id,
    instance_type=instance_type,
    key_name=key_name,
    network_interfaces=[aws.ec2.LaunchTemplateNetworkInterfaceArgs(
        associate_public_ip_address="true",
        security_groups=[application_sg.id],
        subnet_id=public_subnets[0],
    )],
    iam_instance_profile=aws.ec2.LaunchTemplateIamInstanceProfileArgs(
        name=instance_profile.name,
    ),
    user_data = pulumi.Output.all(db_endpoint = database_instance.endpoint,
    sns_arn = sns_topic.arn
    ).apply(
        lambda  args: base64.b64encode(f"""#!/bin/bash
NEW_DB_USER={DB_USER}
NEW_DB_PASSWORD={DB_PASSWORD}
NEW_DB_HOST={args["db_endpoint"].split(":")[0]}
NEW_DB_NAME={DB_NAME}
ENV_FILE_PATH={ENV_FILE_PATH}
NEW_SNS_TOPIC_ARN={args["sns_arn"]}
NEW_AWS_REGION={aws_region}

if [ -e "$ENV_FILE_PATH" ]; then
sed -i -e "s/DB_HOST=.*/DB_HOST=$NEW_DB_HOST/" \
-e "s/DB_USER=.*/DB_USER=$NEW_DB_USER/" \
-e "s/DB_PASSWORD=.*/DB_PASSWORD=$NEW_DB_PASSWORD/" \
-e "s/DB_NAME=.*/DB_NAME=$NEW_DB_NAME/" \
-e "s/SNS_TOPIC_ARN=.*/SNS_TOPIC_ARN=$NEW_SNS_TOPIC_ARN/" \
-e "s/AWS_REGION=.*/AWS_REGION=$NEW_AWS_REGION/" \
"$ENV_FILE_PATH"
else
echo "$ENV_FILE_PATH not found. Make sure the .env file exists"
fi
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -c file:/opt/csye6225/webapp/cloudwatch-config.json \
    -s""".encode()).decode('utf-8')
    ),
    tag_specifications=[aws.ec2.LaunchTemplateTagSpecificationArgs(
        resource_type="instance",
        tags={
            "Name": "application instance",
        },
    )],
)

asg = aws.autoscaling.Group("asg",
    name="demoasg",
    desired_capacity=1,
    max_size=3,
    min_size=1,
    default_cooldown=60,
    health_check_grace_period=200,
    health_check_type="ELB",
    vpc_zone_identifiers=public_subnets,
    launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
        id=my_instance_template.id,
        version="$Latest",
    ),
    tags=[
        aws.autoscaling.GroupTagArgs(
            key='Name',
            value='application instance',
            propagate_at_launch=True,
        )
    ])

scale_up_policy = aws.autoscaling.Policy("scale-up-policy",
    scaling_adjustment=1,
    adjustment_type="ChangeInCapacity",
    cooldown=60,
    autoscaling_group_name=asg.name,
)

scale_down_policy = aws.autoscaling.Policy("scale-down-policy",
    scaling_adjustment=-1,
    adjustment_type="ChangeInCapacity",
    cooldown=60,  
    autoscaling_group_name=asg.name,
)

scale_up_alarm = aws.cloudwatch.MetricAlarm("scale-up-alarm",
    comparison_operator="GreaterThanOrEqualToThreshold",
    evaluation_periods=1,
    metric_name="CPUUtilization",
    namespace="AWS/EC2",
    period=300,
    statistic="Average",
    threshold=5,
    dimensions= {
        "AutoScalingGroupName": asg.name,
    },
    alarm_actions=[scale_up_policy.arn],
)

scale_down_alarm = aws.cloudwatch.MetricAlarm("scale-down-alarm",
    comparison_operator="LessThanOrEqualToThreshold",
    evaluation_periods=1,
    metric_name="CPUUtilization",
    namespace="AWS/EC2",
    period=300,
    statistic="Average",
    threshold=3,
    dimensions= {
        "AutoScalingGroupName": asg.name,
    },
    alarm_actions=[scale_down_policy.arn],
)

alb = aws.lb.LoadBalancer("alb",
    internal=False,
    load_balancer_type="application",
    security_groups=[loadbalancer_sg.id],
    subnets=public_subnets,
    tags={
        "Environment": "dev",
    })
certificate_issued = aws.acm.get_certificate(domain=DOMAIN,
    most_recent=True,
    statuses=["ISSUED"])

targetGroup = aws.lb.TargetGroup("targetGroup",
    port=3000,
    protocol="HTTP",
    vpc_id=create_vpc.id,
    health_check=aws.lb.TargetGroupHealthCheckArgs(
        path='/healthz',
        port=3000
    ))

listener = aws.lb.Listener("listener",
    load_balancer_arn=alb.arn,
    port=443,
    protocol="HTTPS",
    certificate_arn = certificate_issued.arn,
    default_actions=[aws.lb.ListenerDefaultActionArgs(
        type="forward",
        target_group_arn=targetGroup.arn,
    )])

asg_lb_attachment = aws.autoscaling.Attachment("asg_lb_attachment",
    autoscaling_group_name=asg.id,
    lb_target_group_arn=targetGroup.arn)



selected = aws.route53.get_zone(name=domain_name,
    private_zone=False)
www = aws.route53.Record("www",
    zone_id=selected.zone_id,
    name=f"{selected.name}",
    type="A",
    aliases=[aws.route53.RecordAliasArgs(
        name=alb.dns_name,
        zone_id=alb.zone_id,
        evaluate_target_health=True,
    )])



pulumi.export(vpc_name, create_vpc.id)
pulumi.export(igw_name, create_igw.id)
for i, subnet in enumerate(public_subnets):
    pulumi.export(f'publicsubnet-{i + 1}', subnet)
for i, subnet in enumerate(private_subnets):
    pulumi.export(f'privatesubnet-{i + 1}', subnet)
pulumi.export('az', zones)
pulumi.export("availability_zone_count", availability_zone_count)

