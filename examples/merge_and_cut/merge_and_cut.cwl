---
class: Workflow
cwlVersion: v1.0
inputs:
   smallfiles:
     type:
       type: array
       items:
         type: array
         items:
           type: array
           items: File
outputs:
  - 
    id: "#merged_and_cut"
    type: File
    outputSource: "#cut/cut1"
steps:
  -
    id: "#merge"
    run: "merge.cwl"
    in:
    - 
      id: "#merge/smallfiles"
      source: "smallfiles"
    scatter: "#merge/smallfiles"
    out:
    -
      id: "#merge/merged"
  -
    id: "#cut"
    run: "cut.cwl"
    in:
    - 
      id: "#cut/files"
      source: "#merge/merged"
    out:
    -
      id: "#cut/cut1"
requirements:
  -
    class: "ScatterFeatureRequirement"
  -
    class: "SubworkflowFeatureRequirement"

