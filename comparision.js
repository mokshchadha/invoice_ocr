const fs = require('fs').promises;
const path = require('path');
const { GoogleGenAI } = require('@google/genai');

const CONFIG = {
  inputFolder: './invoices',
  outputFolder: './results',
  apiKey: process.env.GEMINI_API_KEY, 
  models: [
    'gemini-2.0-flash-lite',  
    'gemini-2.0-flash', 
    'gemini-2.5-flash',       
    'gemini-2.5-pro'          
  ],
  sourceOfTruthModel: 'gemini-2.5-pro',
  modelConfig: {
    temperature: 0,
    topP: 0.1,
    topK: 1,
    maxOutputTokens: 8192,
    responseMimeType: 'application/json',
    candidateCount: 1,
    safetySettings: [
      {
        category: 'HARM_CATEGORY_HARASSMENT',
        threshold: 'BLOCK_NONE'
      },
      {
        category: 'HARM_CATEGORY_HATE_SPEECH',
        threshold: 'BLOCK_NONE'
      },
      {
        category: 'HARM_CATEGORY_SEXUALLY_EXPLICIT',
        threshold: 'BLOCK_NONE'
      },
      {
        category: 'HARM_CATEGORY_DANGEROUS_CONTENT',
        threshold: 'BLOCK_NONE'
      }
    ]
  }
};

// Initialize AI with correct constructor pattern
const ai = new GoogleGenAI({ apiKey: CONFIG.apiKey });

const EXTRACTION_PROMPT = `I want you to process the document with high accuracy to generate the following fields and return a json document with filled information 
  {
  "IRN_Number": "Unique Invoice Reference Number generated after e-invoice is pushed to IRP.",
  "invoice_date": "Date on which invoice is created. should be today or yesterday.",
  "supplier_gst": "GST identification number of the supplier.",
  "supplier_name": "Supplier entity name involved in the order.",
  "buyer_gst": "GST identification number of the buyer. Should start from SPCX",
  "buyer_name": "Buyer entity to whom material is sold. Should be company name 'SPCX PVT LTD'.",
  "buyer_billing_address": "Billing address of the buyer, GST address of SPCX godown locations. ",
  "ship_to_address": "Shipping address on invoice should be loading address of the supplier ",
  "delivery_terms": "Delivery terms specification, typically 'EX GODOWN'.",
  "vehicle_number": "Vehicle number for the order. Stored in internal database.",
  "grade_number": "Product grade number extracted from product .",
  "hsn_number": "Mandatory 6-digit HSN code with starting 4 digits match requirement.",
  "supplier_price": "Supplier price calculated as SP + SCN (Supplier Price + Supply Chain Network).",
  "quantity": "a number field quantity in KG",
  "total_amount": "Total calculated amount stored as amount field.",
  "invoice_number": "Supplier nomenclature of the invoice."
}


NOTE: If the image is blurry or some information is missing then leave that part as empty string and highlight what parts are missing and why. Return only valid JSON format.`;

class AIAdapter {
  constructor(apiKey) {
  }

  async askAI(filePath, modelName, prompt) {
    try {
      console.log(`Processing ${path.basename(filePath)} with ${modelName}...`);
      
      const fileBuffer = await fs.readFile(filePath);
      const imagePart = {
        inlineData: {
          data: fileBuffer.toString('base64'),
          mimeType: 'application/pdf'
        }
      };
      
      const textPart = { text: prompt };
      
      const response = await ai.models.generateContent({
        model: modelName,
        contents: [textPart, imagePart],
        config: CONFIG.modelConfig
      });
      
      const text = response.text;
      return this.parseJSONFromResponse(text);
      
    } catch (error) {
      console.error(`Error processing with ${modelName}:`, error.message);
      return {
        error: error.message,
        rawResponse: null
      };
    }
  }

  parseJSONFromResponse(responseText) {
    try {
      const jsonMatch = responseText.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      } else {
        return JSON.parse(responseText);
      }
    } catch (error) {
      console.warn('Failed to parse JSON from response');
      return {
        error: 'Invalid JSON response',
        rawResponse: responseText
      };
    }
  }
}

class FileUtils {
  static async getPDFFiles(folderPath) {
    try {
      const files = await fs.readdir(folderPath);
      return files
        .filter(file => path.extname(file).toLowerCase() === '.pdf')
        .map(file => path.join(folderPath, file));
    } catch (error) {
      console.error('Error reading folder:', error.message);
      return [];
    }
  }

  static async ensureDirectory(dirPath) {
    try {
      await fs.mkdir(dirPath, { recursive: true });
    } catch (error) {
      console.error('Error creating directory:', error.message);
    }
  }

  static async saveResults(filePath, data) {
    try {
      await fs.writeFile(filePath, JSON.stringify(data, null, 2), 'utf8');
      console.log(`Results saved to ${filePath}`);
    } catch (error) {
      console.error('Error saving results:', error.message);
    }
  }
}

class ResultComparator {
  static normalizeString(value) {
  if (typeof value !== 'string') {
    return value;
  }
  
  let normalized = value
    .replace(/Α/g, 'A')  // Greek Alpha to Latin A
    .replace(/α/g, 'a')  // Greek alpha to Latin a
    .replace(/Ι/g, 'I')  // Greek Iota to Latin I
    .replace(/ι/g, 'i')  // Greek iota to Latin i
    .replace(/Ο/g, 'O')  // Greek Omicron to Latin O
    .replace(/ο/g, 'o')  // Greek omicron to Latin o
    .replace(/Ε/g, 'E')  // Greek Epsilon to Latin E
    .replace(/ε/g, 'e')  // Greek epsilon to Latin e
    .replace(/Η/g, 'H')  // Greek Eta to Latin H
    .replace(/η/g, 'h')  // Greek eta to Latin h
    .replace(/Κ/g, 'K')  // Greek Kappa to Latin K
    .replace(/κ/g, 'k')  // Greek kappa to Latin k
    .replace(/Μ/g, 'M')  // Greek Mu to Latin M
    .replace(/μ/g, 'm')  // Greek mu to Latin m
    .replace(/Ν/g, 'N')  // Greek Nu to Latin N
    .replace(/ν/g, 'n')  // Greek nu to Latin n
    .replace(/Ρ/g, 'R')  // Greek Rho to Latin R
    .replace(/ρ/g, 'r')  // Greek rho to Latin r
    .replace(/Τ/g, 'T')  // Greek Tau to Latin T
    .replace(/τ/g, 't')  // Greek tau to Latin t
    .replace(/Υ/g, 'Y')  // Greek Upsilon to Latin Y
    .replace(/υ/g, 'y')  // Greek upsilon to Latin y
    .replace(/Χ/g, 'X')  // Greek Chi to Latin X
    .replace(/χ/g, 'x')  // Greek chi to Latin x
    .replace(/Ζ/g, 'Z')  // Greek Zeta to Latin Z
    .replace(/ζ/g, 'z'); // Greek zeta to Latin z
  
  // Convert to lowercase and remove all non-alphanumeric characters
  return normalized.toLowerCase().replace(/[^a-z0-9]/g, '');
}

  static valuesMatch(value1, value2) {
    if (value1 == null && value2 == null) return true;
    if (value1 == null || value2 == null) return false;
    
    if (typeof value1 === 'string' || typeof value2 === 'string') {
      return this.normalizeString(value1) === this.normalizeString(value2);
    }
    
    return value1 === value2;
  }


  static shouldExcludeField(fieldPath) {
  const excludedPaths = [
    'addressDetails',
    'addressDetails.billingAddress',
    'addressDetails.billingAddress.billToName',
    'addressDetails.billingAddress.billToAddress',
    'addressDetails.shippingAddress',
    'addressDetails.shippingAddress.shipToName',
    'addressDetails.shippingAddress.shipToAddress',
    'vendorDetails.address',
    'transportDetails.loadingAddress',
    // Add GST fields to exclusion list
    'vendorDetails.gstInternalAmount',
    'vendorDetails.gstAmount'
  ];
  
  return excludedPaths.some(excluded => 
    fieldPath === excluded || fieldPath.startsWith(excluded + '.')
  );
}


  static filterAddressDetails(obj) {
    if (!obj || typeof obj !== 'object') return obj;
    
    const filtered = {};
    
    for (const [key, value] of Object.entries(obj)) {
      if (key === 'addressDetails') {
        continue;
      } else if (key === 'vendorDetails' && value && typeof value === 'object') {
        filtered[key] = {};
        for (const [vendorKey, vendorValue] of Object.entries(value)) {
          if (vendorKey !== 'address') {
            filtered[key][vendorKey] = vendorValue;
          }
        }
      } else if (key === 'transportDetails' && value && typeof value === 'object') {
        filtered[key] = {};
        for (const [transportKey, transportValue] of Object.entries(value)) {
          if (transportKey !== 'loadingAddress') {
            filtered[key][transportKey] = transportValue;
          }
        }
      } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        filtered[key] = this.filterAddressDetails(value);
      } else {
        filtered[key] = value;
      }
    }
    
    return filtered;
  }

  static compareResults(results, sourceOfTruth) {
    const comparison = {
      sourceOfTruth: sourceOfTruth,
      analysis: {},
      summary: {
        totalFiles: Object.keys(results).length,
        modelAccuracy: {},
        commonMissingFields: {},
        modelErrors: {}
      },
      note: "Address details are excluded from this comparison"
    };

    for (const [fileName, fileResults] of Object.entries(results)) {
      comparison.analysis[fileName] = this.compareFileResults(fileResults, sourceOfTruth);
    }

    this.generateSummary(comparison, results);

    return comparison;
  }

  static compareFileResults(fileResults, sourceOfTruth) {
    const truthData = fileResults[sourceOfTruth];
    const comparison = {
      sourceOfTruthHasError: !!truthData?.error,
      modelComparisons: {}
    };

    if (!truthData || truthData.error) {
      comparison.note = "Source of truth model failed or has errors";
      return comparison;
    }

    for (const [modelName, modelResult] of Object.entries(fileResults)) {
      if (modelName === sourceOfTruth) continue;

      comparison.modelComparisons[modelName] = this.compareModelResults(
        modelResult, 
        truthData, 
        modelName
      );
    }

    return comparison;
  }

  static compareModelResults(modelResult, truthResult, modelName) {
    const comparison = {
      hasError: !!modelResult?.error,
      matchingFields: 0,
      totalFields: 0,
      missingFields: [],
      differentValues: [],
      accuracy: 0,
      note: "Address details excluded from comparison"
    };

    if (modelResult?.error) {
      comparison.error = modelResult.error;
      return comparison;
    }

    const filteredModelResult = this.filterAddressDetails(modelResult);
    const filteredTruthResult = this.filterAddressDetails(truthResult);

    this.deepCompare(filteredModelResult, filteredTruthResult, comparison, '');

    if (comparison.totalFields > 0) {
      comparison.accuracy = (comparison.matchingFields / comparison.totalFields) * 100;
    }

    return comparison;
  }

  static deepCompare(obj1, obj2, comparison, prefix) {
    for (const key in obj2) {
      const fullKey = prefix ? `${prefix}.${key}` : key;
      if (this.shouldExcludeField(fullKey)) {
        continue;
      }
      
      comparison.totalFields++;

      if (typeof obj2[key] === 'object' && obj2[key] !== null && !Array.isArray(obj2[key])) {
        if (obj1[key] && typeof obj1[key] === 'object') {
          this.deepCompare(obj1[key], obj2[key], comparison, fullKey);
        } else {
          comparison.missingFields.push(fullKey);
        }
      } else {
        if (this.valuesMatch(obj1[key], obj2[key])) {
          comparison.matchingFields++;
        } else if (obj1[key] === undefined || obj1[key] === null || obj1[key] === '') {
          comparison.missingFields.push(fullKey);
        } else {
          comparison.differentValues.push({
            field: fullKey,
            modelValue: obj1[key],
            truthValue: obj2[key],
            normalizedModelValue: this.normalizeString(obj1[key]),
            normalizedTruthValue: this.normalizeString(obj2[key])
          });
        }
      }
    }
  }

  static generateSummary(comparison, results) {
    const models = CONFIG.models.filter(m => m !== CONFIG.sourceOfTruthModel);
    
    models.forEach(model => {
      comparison.summary.modelAccuracy[model] = [];
      comparison.summary.modelErrors[model] = 0;
    });

    for (const fileAnalysis of Object.values(comparison.analysis)) {
      if (fileAnalysis.sourceOfTruthHasError) continue;

      for (const [modelName, modelComparison] of Object.entries(fileAnalysis.modelComparisons)) {
        if (modelComparison.hasError) {
          comparison.summary.modelErrors[modelName]++;
        } else {
          comparison.summary.modelAccuracy[modelName].push(modelComparison.accuracy);
        }
      }
    }

    for (const model of models) {
      const accuracies = comparison.summary.modelAccuracy[model];
      if (accuracies.length > 0) {
        const avgAccuracy = accuracies.reduce((sum, acc) => sum + acc, 0) / accuracies.length;
        comparison.summary.modelAccuracy[model] = {
          average: Math.round(avgAccuracy * 100) / 100,
          count: accuracies.length,
          details: accuracies
        };
      } else {
        comparison.summary.modelAccuracy[model] = {
          average: 0,
          count: 0,
          details: []
        };
      }
    }
  }
}
class InvoiceProcessor {
  constructor() {
    this.aiAdapter = new AIAdapter(CONFIG.apiKey);
    this.results = {};
  }

  async processAllFiles() {
    console.log('Starting PDF invoice processing...');
    
    await FileUtils.ensureDirectory(CONFIG.outputFolder);

    const pdfFiles = await FileUtils.getPDFFiles(CONFIG.inputFolder);
    
    if (pdfFiles.length === 0) {
      console.log('No PDF files found in the input folder.');
      return;
    }

    console.log(`Found ${pdfFiles.length} PDF files to process.`);

    for (const filePath of pdfFiles) {
      const fileName = path.basename(filePath);
      console.log(`\n--- Processing ${fileName} ---`);
      
      this.results[fileName] = {};

      for (const modelName of CONFIG.models) {
        const result = await this.aiAdapter.askAI(filePath, modelName, EXTRACTION_PROMPT);
        this.results[fileName][modelName] = result;
        
        await this.delay(1000);
      }
    }

    const resultsPath = path.join(CONFIG.outputFolder, 'extraction_results.json');
    await FileUtils.saveResults(resultsPath, this.results);

    const comparison = ResultComparator.compareResults(this.results, CONFIG.sourceOfTruthModel);
    const comparisonPath = path.join(CONFIG.outputFolder, 'model_comparison.json');
    await FileUtils.saveResults(comparisonPath, comparison);

    await this.generateSummaryReport(comparison);

    console.log('\n--- Processing Complete ---');
    console.log(`Results saved in: ${CONFIG.outputFolder}`);
  }

async generateSummaryReport(comparison) {
  const report = `# Invoice Processing Model Comparison Report

**Generated:** ${new Date().toISOString()}
**Source of Truth Model:** ${comparison.sourceOfTruth}
**Total Files Processed:** ${comparison.summary.totalFiles}

## Model Performance Summary

${Object.entries(comparison.summary.modelAccuracy).map(([model, accuracy]) => 
`### ${model}
- **Average Accuracy:** ${accuracy.average}%
- **Files Successfully Processed:** ${accuracy.count}
- **Errors:** ${comparison.summary.modelErrors[model]}

`).join('')}`;

  const reportPath = path.join(CONFIG.outputFolder, 'summary_report.md');
  await FileUtils.saveResults(reportPath, report);
}

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

async function main() {
  try {
    if (!CONFIG.apiKey) {
      console.error('Please set GEMINI_API_KEY environment variable');
      process.exit(1);
    }

    const processor = new InvoiceProcessor();
    await processor.processAllFiles();
    
  } catch (error) {
    console.error('Fatal error:', error);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  InvoiceProcessor,
  AIAdapter,
  FileUtils,
  ResultComparator,
  CONFIG
};