terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  backend "s3" {}
}

variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {}

variable "public_key" {}

variable "private_key" {}

variable "db_password" {
  description = "Seed value for the RDS master password (used to rotate the generated password; the raw value is NOT sent to RDS)"
  sensitive   = true
}

variable "db_name" {
  default = "tododb"
}

variable "db_user" {
  default = "todoapp"
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "udap"
    }
  }
}

# ── Safe RDS password ─────────────────────────────────────────────────────────
# RDS forbids '/', '@', '"', and ' ' in the master password.
# We generate a guaranteed-compliant password using random_password.
# The user-supplied db_password is used only as a keeper so the generated
# password rotates automatically whenever the secret value changes.
resource "random_password" "db" {
  length  = 32
  special = true
  # Only include special chars that RDS accepts (excludes / @ " and space)
  override_special = "!#$%&*()-_=+[]{}|;:,.<>?"

  keepers = {
    seed = var.db_password
  }
}

# ── Data ──────────────────────────────────────────────────────────────────────

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd*/ubuntu-*-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ── VPC ───────────────────────────────────────────────────────────────────────

resource "aws_vpc" "uat" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "${var.project_name}-vpc" }
}

# ── Public subnet (EC2) ───────────────────────────────────────────────────────

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = { Name = "${var.project_name}-public-subnet" }

  depends_on = [aws_vpc.main]
}

# ── Private subnets (RDS — two AZs required for subnet group) ─────────────────

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]

  tags = { Name = "${var.project_name}-private-subnet-a" }

  depends_on = [aws_vpc.main]
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = data.aws_availability_zones.available.names[1]

  tags = { Name = "${var.project_name}-private-subnet-b" }

  depends_on = [aws_vpc.main]
}

# ── Internet gateway & routing ────────────────────────────────────────────────

resource "aws_internet_gateway" "uat" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.project_name}-igw" }

  depends_on = [aws_vpc.main]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.project_name}-public-rt" }

  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ── Security groups ───────────────────────────────────────────────────────────

resource "aws_security_group" "app" {
  # name_prefix lets AWS append a unique suffix, so create_before_destroy
  # can create the replacement SG before deleting the old one without hitting
  # the InvalidGroup.Duplicate error that a fixed `name` causes.
  name_prefix = "${var.project_name}-app-sg-"
  description = "Security group for ${var.project_name} app server"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "App port"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-app-sg" }

  depends_on = [aws_vpc.main]

  lifecycle {
    create_before_destroy = true
    # Ignore the generated suffix Terraform sees after the first apply,
    # preventing a perpetual diff on the name field.
    ignore_changes = [name]
  }
}

resource "aws_security_group" "rds" {
  # Same name_prefix pattern for consistency and safe replacement.
  name_prefix = "${var.project_name}-rds-sg-"
  description = "Allow PostgreSQL access from app server only"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-rds-sg" }

  depends_on = [aws_vpc.main]

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [name]
  }
}

# Separate rule so that the cross-SG reference can be removed before either SG
# is destroyed, preventing the DependencyViolation on teardown.
resource "aws_security_group_rule" "rds_from_app" {
  type                     = "ingress"
  description              = "PostgreSQL from app"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.app.id
}

# ── RDS subnet group ──────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "uat" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  tags = { Name = "${var.project_name}-db-subnet-group" }

  depends_on = [aws_subnet.private_a, aws_subnet.private_b]
}

# ── RDS PostgreSQL ────────────────────────────────────────────────────────────

resource "aws_db_instance" "uat" {
  identifier        = "${var.project_name}-db"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_user
  # Use the generated, RDS-compliant password — never the raw secret which
  # may contain forbidden characters (/, @, ", space).
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible       = false
  multi_az                  = false
  deletion_protection       = false
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project_name}-db-final-snapshot"

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  auto_minor_version_upgrade = true

  tags = { Name = "${var.project_name}-db" }

  depends_on = [aws_db_subnet_group.main]
}

# ── EC2 key pair ──────────────────────────────────────────────────────────────

resource "aws_key_pair" "app" {
  key_name   = "${var.project_name}-keypair"
  public_key = var.public_key

  tags = { Name = "${var.project_name}-keypair" }
}

resource "local_file" "private_key" {
  content         = var.private_key
  filename        = "${path.module}/../.ssh/id_rsa"
  file_permission = "0600"
}

# ── EC2 instance ──────────────────────────────────────────────────────────────

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  key_name               = aws_key_pair.app.key_name

  tags = {
    Name    = "${var.project_name}-app"
    Project = var.project_name
  }

  depends_on = [aws_subnet.public, aws_security_group.app]
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = { Name = "${var.project_name}-eip" }
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "instance_public_ip" {
  value = aws_eip.app.public_ip
}

output "app_url" {
  value = "http://${aws_eip.app.public_ip}"
}

output "rds_endpoint" {
  value       = aws_db_instance.main.address
  description = "RDS hostname (no port)"
}

output "rds_port" {
  value       = aws_db_instance.main.port
  description = "RDS port"
}

output "rds_db_name" {
  value = aws_db_instance.main.db_name
}

output "rds_username" {
  value = aws_db_instance.main.username
}

output "rds_password" {
  value     = random_password.db.result
  sensitive = true
}
