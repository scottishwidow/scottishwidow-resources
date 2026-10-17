removed {
  from = module.vpc

  lifecycle {
    destroy = false
  }
}

removed {
  from = module.next_cloud

  lifecycle {
    destroy = false
  }
}

removed {
  from = module.next_cloud_sg

  lifecycle {
    destroy = false
  }
}

removed {
  from = module.next_cloud_backup

  lifecycle {
    destroy = false
  }
}

removed {
  from = module.ssm_scratch

  lifecycle {
    destroy = false
  }
}
