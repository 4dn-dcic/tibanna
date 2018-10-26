---
class: Workflow
cwlVersion: v1.0
inputs:
   smallfiles:
     type:
       type: array
       items:
         type: array
         items: File
outputs:
  - 
    id: "#merged"
    type: File
    outputSource: "#cat/concatenated"
steps:
  -
    id: "#paste"
    run: "paste.cwl"
    in:
    - 
      id: "#paste/files"
      source: "smallfiles"
    scatter: "#paste/files"
    out:
    -
      id: "#paste/pasted"
  -
    id: "#cat"
    run: "cat.cwl"
    in:
    - 
      id: "#cat/files"
      source: "#paste/pasted"
    out:
    -
      id: "#cat/concatenated"
requirements:
  -
    class: "ScatterFeatureRequirement"
