---
class: CommandLineTool
cwlVersion: v1.0
baseCommand:
  - "cat"
inputs:
  - id: "#files"
    type: array
    items: File
    inputBinding:
      position: 1
outputs:
  - id: "#concatenated"
    type: File
    streamable: true
    outputBinding:
      glob: "concatenated"
stdout: "concatenated"
hints:
  - dockerPull: ubuntu:16.4
    class: DockerRequirement
