---
cwlVersion: v1.0
baseCommand:
  - split
inputs:
  - id: lines
    type:
      - Int
    inputBinding:
      prefix: -l
      position: 1
  - id: inputfile
    type:
      - File
    inputBinding:
      position: 2
  - id: outprefix
    type:
      - String
    inputBinding:
      position: 3
      default: split-out-
outputs:
  - id: output
    type:
    - File
    outputBinding:
      glob: $(inputs.outprefix + '*')
hints:
  - dockerPull: ubuntu:16.04
    class: DockerRequirement
class: CommandLineTool

