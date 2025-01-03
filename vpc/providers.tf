terraform {
  backend "s3" {
    bucket = ""
    key = "backend.tfstate"
    region = ""
    dynamodb_table = ""
    encrypt = true
  }
}