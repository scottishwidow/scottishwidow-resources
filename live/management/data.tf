# Canonical publishes the latest Ubuntu AMI IDs as public SSM parameters.
# Path format: /aws/service/canonical/ubuntu/<product>/<release>/stable/current/<arch>/hvm/<vol-type>/ami-id
# "current" always resolves to the newest published image for the release.
data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server-minimal/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}
