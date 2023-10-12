import pulumi
import pulumi_aws as aws

config = pulumi.Config()
vpc_name = config.require('vpc_name')
igw_name = config.require('myigw_name')
public_subnets_config = config.require_object('public_subnets_config')
private_subnets_config = config.require_object('private_subnets_config')
destination_route_cidr = config.require('destination_route_cidr')

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

public_subnets = []
private_subnets = []
for config in public_subnets_config:
    subnet = aws.ec2.Subnet(config["name"],
        vpc_id=create_vpc.id,
        cidr_block=config["cidr_block"],
        availability_zone=config["az"],  # Set your desired availability zone
        tags={"Name": config["name"]},
    )
    public_subnets.append(subnet)

for config in private_subnets_config:
    subnet = aws.ec2.Subnet(config["name"],
        vpc_id=create_vpc.id,
        cidr_block=config["cidr_block"],
        availability_zone=config["az"],  # Set your desired availability zone
        tags={"Name": config["name"]},
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

pulumi.export(vpc_name, create_vpc.id)
pulumi.export(igw_name, create_igw.id)
for i, subnet in enumerate(public_subnets):
    pulumi.export(f'publicsubnet-{i + 1}', subnet.id)
for i, subnet in enumerate(private_subnets):
    pulumi.export(f'privatesubnet-{i + 1}', subnet.id)

