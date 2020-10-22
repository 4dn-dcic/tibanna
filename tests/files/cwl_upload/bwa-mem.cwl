{
  "hints": [
    {
      "dockerPull": "duplexa/4dn-hic:v42.1",
      "class": "DockerRequirement"
    }
  ],
  "arguments": [],
  "class": "CommandLineTool",
  "inputs": [
    {
      "type": [
        "File"
      ],
      "id": "#fastq1",
      "inputBinding": {
        "position": 1,
        "separate": true
      }
    },
    {
      "type": [
        "File"
      ],
      "id": "#fastq2",
      "inputBinding": {
        "position": 2,
        "separate": true
      }
    },
    {
      "type": [
        "File"
      ],
      "id": "#bwa_index",
      "inputBinding": {
        "position": 3,
        "separate": true
      }
    },
    {
      "type": [
        "int"
      ],
      "id": "#nThreads",
      "inputBinding": {
        "position": 6,
        "separate": true
      },
      "default": 4
    },
    {
      "type": [
        "null",
        "string"
      ],
      "id": "#prefix",
      "inputBinding": {
        "position": 5,
        "separate": true
      },
      "default": "out"
    },
    {
      "type": [
        "null",
        "string"
      ],
      "id": "#outdir",
      "inputBinding": {
        "position": 4,
        "separate": true
      },
      "default": "."
    }
  ],
  "outputs": [
    {
      "type": [
        "null",
        "File"
      ],
      "id": "#out_bam",
      "outputBinding": {
        "glob": "*.bam"
      }
    }
  ],
  "baseCommand": [
    "run-bwa-mem.sh"
  ],
  "requirements": [
    {
      "class": "InlineJavascriptRequirement"
    }
  ],
  "cwlVersion": "v1.0"
}
