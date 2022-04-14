{ lib, python3Packages }:
with python3Packages;
buildPythonApplication {
  pname = "plover-stenohid-experiment";
  version = "0.1.0.dev2";

  nativeBuildInputs = [ setuptools_scm ];
  propagatedBuildInputs = [ pyudev ];

  doCheck = false;

  src = ./.;
}
