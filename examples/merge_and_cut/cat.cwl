---
class: CommandLineTool
cwlVersion: v1.0
baseCommand:
  - "cat"
inputs:
  files:
    type:
      type: array
      items: File
    inputBinding:
      position: 1
outputs:
  - id: "concatenated"
    type: File
    streamable: true
    outputBinding:
      glob: "concatenated"
stdout: "concatenated"
hints:
  - dockerPull: ubuntu:16.04
    class: DockerRequirement
