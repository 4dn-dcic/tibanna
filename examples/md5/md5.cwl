---
cwlVersion: v1.0
inputs:
- id: "#input_file"
  type:
  - File
  inputBinding:
    position: 1
outputs:
- id: "#report"
  type:
  - File
  outputBinding:
    glob: report
hints:
- dockerPull: duplexa/md5:v2
  class: DockerRequirement
baseCommand:
- run.sh
class: CommandLineTool

