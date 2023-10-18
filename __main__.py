import pulumi
import pulumi_aws as aws

zones = []
public_subnets = []
private_subnets = []

config = pulumi.Config()
vpc_name = config.require('vpc_name')
igw_name = config.require('myigw_name')
public_subnets_config = config.require_object('public_subnets_config')
private_subnets_config = config.require_object('private_subnets_config')
destination_route_cidr = config.require('destination_route_cidr')
ami_id = config.require('ami_id')
key_name = config.require('key_name')

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
    public_subnets.append(subnet)

for i,zone in enumerate(zones):
    subnet = aws.ec2.Subnet(private_subnets_config[i]["name"],
    vpc_id=create_vpc.id,
    cidr_block=private_subnets_config[i]["cidr_block"],
    availability_zone = zone,
    tags={"Name": private_subnets_config[i]["name"]},
    )
    private_subnets.append(subnet)

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

for n,subnet in enumerate(public_subnets):
    route_table_association = aws.ec2.RouteTableAssociation(f"myAssociation{n}",
    subnet_id=subnet.id,
    route_table_id=public_route_table.id,
    )
for n,subnet in enumerate(private_subnets, start=4):
    route_table_association = aws.ec2.RouteTableAssociation(f"myAssociation{n}",
    subnet_id=subnet.id,
    route_table_id=private_route_table.id,
    )

my_sg = aws.ec2.SecurityGroup("application security group",
    description="Allow SSH, HTTP, HTTPS, WEBAPP_PORT",
    vpc_id=create_vpc.id,
    ingress=[aws.ec2.SecurityGroupIngressArgs(
        description="SSH",
        from_port=22,
        to_port=22,
        protocol="tcp",
        cidr_blocks=['155.33.132.45/32'],
    ),
    aws.ec2.SecurityGroupIngressArgs(
        description="HTTP",
        from_port=80,
        to_port=80,
        protocol="tcp",
        cidr_blocks=['0.0.0.0/0'],
    ),
    aws.ec2.SecurityGroupIngressArgs(
        description="HTTPS",
        from_port=443,
        to_port=443,
        protocol="tcp",
        cidr_blocks=["0.0.0.0/0"],
    ),
    aws.ec2.SecurityGroupIngressArgs(
        description="WEBAPP_PORT",
        from_port=3000,
        to_port=3000,
        protocol="tcp",
        cidr_blocks=['0.0.0.0/0'],
    )],
    tags={
        "Name": "application security group",
    })

my_instance = aws.ec2.Instance("my_instance", 
    ami= ami_id,
    instance_type="t2.micro",
    security_groups=[my_sg.id],
    subnet_id=public_subnets[0].id,
    associate_public_ip_address=True,
    key_name=key_name,
    root_block_device={
        "volume_size": 25,
        "volume_type": "gp2",
        "delete_on_termination": True,
    },
    tags={
        "Name": "application instance",
    }
)

pulumi.export(vpc_name, create_vpc.id)
pulumi.export(igw_name, create_igw.id)
for i, subnet in enumerate(public_subnets):
    pulumi.export(f'publicsubnet-{i + 1}', subnet.id)
for i, subnet in enumerate(private_subnets):
    pulumi.export(f'privatesubnet-{i + 1}', subnet.id)
pulumi.export('az', zones)
pulumi.export("availability_zone_count", availability_zone_count)

