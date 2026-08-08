# OS-level configuration for the Voice-AI GPU node: base packages, Docker,
# the k8s tooling snaps (microk8s, helm, kubectl, k9s) and the NVIDIA driver.
# Every resource is guarded so re-running the plan is a no-op once converged.
class voice_ai::node (
  String[1]                 $node_user,
  Array[String[1]]          $base_packages,
  Hash[String[1], String]   $snaps,
  Boolean                   $manage_docker = true,
  Boolean                   $manage_nvidia = true,
) {

  exec { 'apt-update':
    command => 'apt-get update',
    path    => ['/usr/bin', '/bin'],
  }

  package { $base_packages:
    ensure  => installed,
    require => Exec['apt-update'],
  }

  if $manage_docker {
    exec { 'install-docker':
      command => 'curl -fsSL https://get.docker.com | sh',
      path    => ['/usr/bin', '/bin', '/usr/sbin', '/sbin'],
      creates => '/usr/bin/docker',
      require => Package[$base_packages],
    }

    exec { "docker-group-${node_user}":
      command => "usermod -aG docker ${node_user}",
      path    => ['/usr/sbin', '/usr/bin', '/bin'],
      unless  => "id -nG ${node_user} | grep -qw docker",
      require => Exec['install-docker'],
    }
  }

  $snaps.each |String $snap, String $flag| {
    $flagopt = $flag ? { '' => '', default => "--${flag}" }
    exec { "snap-install-${snap}":
      command => "snap install ${snap} ${flagopt}",
      path    => ['/usr/bin', '/bin', '/snap/bin'],
      unless  => "snap list ${snap}",
    }
  }

  exec { "microk8s-group-${node_user}":
    command => "usermod -aG microk8s ${node_user}",
    path    => ['/usr/sbin', '/usr/bin', '/bin'],
    unless  => "id -nG ${node_user} | grep -qw microk8s",
    require => Exec['snap-install-microk8s'],
  }

  if $manage_nvidia {
    exec { 'nvidia-driver':
      command => 'ubuntu-drivers install --gpgpu',
      path    => ['/usr/bin', '/bin', '/usr/sbin', '/sbin'],
      unless  => 'nvidia-smi',
      timeout => 1800,
      require => Package['ubuntu-drivers-common'],
    }
  }
}
