---
class: CommandLineTool
cwlVersion: v1.0
baseCommand:
  - "paste"
inputs:
  files:
    type:
      type: array
      items: File
    inputBinding:
      position: 1
outputs:
  - id: "pasted"
    type: File
    streamable: true
    outputBinding:
      glob: "pasted"
stdout: "pasted"
hints:
  - dockerPull: ubuntu:20.04
    class: DockerRequirement
