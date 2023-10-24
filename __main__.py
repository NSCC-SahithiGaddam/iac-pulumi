import pulumi
import pulumi_aws as aws

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
    db_name="csye6225",
    db_subnet_group_name=database_subnet_group.name,
    engine="mariadb",
    engine_version="10.6",
    identifier="csye6225",
    instance_class="db.t2.micro",
    multi_az=False,
    publicly_accessible= False,
    parameter_group_name=mariadb_parameter_group.name,
    password="passworD99",
    skip_final_snapshot=True,
    username="csye6225",
    vpc_security_group_ids=[database_sg.id])
db_endpoint = database_instance.endpoint.apply(lambda endpoint: f'{endpoint}')

my_instance = aws.ec2.Instance("my_instance", 
    ami= ami_id,
    instance_type=instance_type,
    security_groups=[application_sg.id],
    subnet_id=public_subnets[0],
    associate_public_ip_address=True,
    key_name=key_name,
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
export DB_USER=csye6225
export DB_PASSWORD=passworD99
export DB_HOST={args["db_endpoint"].split(":")[0]}
export PORT=3000
export DB_DIALECT=mysql
export CSV_FILE=/opt/Users.csv
export DB_NAME=csye6225

cat <<EOF > /home/admin/webapp/.env
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=$DB_HOST
PORT=$PORT
DB_DIALECT=$DB_DIALECT
CSV_FILE=$CSV_FILE
DB_NAME=$DB_NAME
EOF""",
    )
)

pulumi.export(vpc_name, create_vpc.id)
pulumi.export(igw_name, create_igw.id)
for i, subnet in enumerate(public_subnets):
    pulumi.export(f'publicsubnet-{i + 1}', subnet)
for i, subnet in enumerate(private_subnets):
    pulumi.export(f'privatesubnet-{i + 1}', subnet)
pulumi.export('az', zones)
pulumi.export("availability_zone_count", availability_zone_count)

