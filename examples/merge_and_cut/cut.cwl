---
class: CommandLineTool
cwlVersion: v1.0
baseCommand:
  - "cut"
  - "-c1"
inputs:
  files:
    type:
      type: array
      items: File
    inputBinding:
      position: 1
outputs:
  - id: "cut1"
    type: File
    streamable: true
    outputBinding:
      glob: "cut1"
stdout: "cut1"
hints:
  - dockerPull: ubuntu:16.04
    class: DockerRequirement
