import pulumi
import pulumi_aws as aws
import json

zones = []
public_subnets = []
private_subnets = []

config = pulumi.Config()
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

application_sg = aws.ec2.SecurityGroup("application security group",
    description="Allow SSH, HTTP, HTTPS, WEBAPP_PORT",
    vpc_id=create_vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        description="SSH",
        from_port=22,
        to_port=22,
        protocol="tcp",
        cidr_blocks=ssh_cidr_blocks,
    ),
    aws.ec2.SecurityGroupIngressArgs(
        description="HTTP",
        from_port=80,
        to_port=80,
        protocol="tcp",
        cidr_blocks=http_cidr_blocks,
    ),
    aws.ec2.SecurityGroupIngressArgs(
        description="HTTPS",
        from_port=443,
        to_port=443,
        protocol="tcp",
        cidr_blocks=https_cidr_blocks,
    ),
    aws.ec2.SecurityGroupIngressArgs(
        description="WEBAPP_PORT",
        from_port=webapp_port,
        to_port=webapp_port,
        protocol="tcp",
        cidr_blocks=webport_cidr_blocks,
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

cloud_watch_role = aws.iam.Role("cloudwatchRole",
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
    roles= [cloud_watch_role.name],
)

instance_profile = aws.iam.InstanceProfile("instanceProfile", role=cloud_watch_role.name)


my_instance = aws.ec2.Instance("my_instance", 
    ami= ami_id,
    instance_type=instance_type,
    security_groups=[application_sg.id],
    subnet_id=public_subnets[0],
    associate_public_ip_address=True,
    key_name=key_name,
    iam_instance_profile= instance_profile.name,
    root_block_device={
        "volume_size": 25,
        "volume_type": "gp2",
        "delete_on_termination": True,
    },
    tags={
        "Name": "application instance",
    },
    user_data = pulumi.Output.all(db_endpoint = database_instance.endpoint
    ).apply(
        lambda  args: f"""#!/bin/bash
NEW_DB_USER={DB_USER}
NEW_DB_PASSWORD={DB_PASSWORD}
NEW_DB_HOST={args["db_endpoint"].split(":")[0]}
NEW_DB_NAME={DB_NAME}
ENV_FILE_PATH={ENV_FILE_PATH}

if [ -e "$ENV_FILE_PATH" ]; then
sed -i -e "s/DB_HOST=.*/DB_HOST=$NEW_DB_HOST/" \
-e "s/DB_USER=.*/DB_USER=$NEW_DB_USER/" \
-e "s/DB_PASSWORD=.*/DB_PASSWORD=$NEW_DB_PASSWORD/" \
-e "s/DB_NAME=.*/DB_NAME=$NEW_DB_NAME/" \
"$ENV_FILE_PATH"
echo "Success"
else
echo "$ENV_FILE_PATH not found. Make sure the .env file exists"
fi
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -c file:/opt/csye6225/webapp/cloudwatch-config.json \
    -s"""
    )
)

selected = aws.route53.get_zone(name="dev.csyenscc.me",
    private_zone=False)
www = aws.route53.Record("www",
    zone_id=selected.zone_id,
    name=f"{selected.name}",
    type="A",
    ttl=300,
    records=[my_instance.public_ip])



pulumi.export(vpc_name, create_vpc.id)
pulumi.export(igw_name, create_igw.id)
for i, subnet in enumerate(public_subnets):
    pulumi.export(f'publicsubnet-{i + 1}', subnet)
for i, subnet in enumerate(private_subnets):
    pulumi.export(f'privatesubnet-{i + 1}', subnet)
pulumi.export('az', zones)
pulumi.export("availability_zone_count", availability_zone_count)

