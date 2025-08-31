// Using Node.js built-in --env-file support (run with: node --env-file=.env script.js)
// Or keep dotenv for compatibility: require('dotenv').config();

// Debug: Check if environment variables are loaded
console.log('Environment variables check:');
console.log('GEMINI_API_KEY:', process.env.GEMINI_API_KEY ? 'Found' : 'Not found');
console.log('All env vars:', Object.keys(process.env).filter(key => key.includes('GEMINI')));

const fs = require('fs').promises;
const path = require('path');
const { GoogleGenAI } = require('@google/genai');

const CONFIG = {
  inputFolder: './invoices',
  outputFolder: './results',
  apiKey: process.env.GEMINI_API_KEY, // Changed from GOOGLE_AI_API_KEY
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
  "vendorDetails": {
    "vendorName": "",
    "gstAvailability": "",
    "gstAmount": "",
    "gstInternalAmount": "",
    "gst": "",
    "address": ""
  },
  "buyerDetails": {
    "buyerName": "",
    "buyerGst": ""
  },
  "invoiceDetails": {
    "invoiceNumber": "",
    "invoiceDate": "",
    "poNumber": "",
    "totalAmount": "",
    "tcsAmount": "",
    "quantity": "",
    "rate": ""
  },
  "addressDetails": {
    "billingAddress": {
      "billToName": "",
      "billToAddress": ""
    },
    "shippingAddress": {
      "shipToName": "",
      "shipToAddress": ""
    }
  },
  "transportDetails": {
    "vehicleNumber": "",
    "loadingAddress": ""
  },
  "productDetails": {
    "productName": ""
  },
  "IRN_Number": ""
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
    return value.toLowerCase().replace(/[\s\n\t]+/g, ' ').trim();
  }

  static valuesMatch(value1, value2) {
    if (value1 == null && value2 == null) return true;
    if (value1 == null || value2 == null) return false;
    
    if (typeof value1 === 'string' || typeof value2 === 'string') {
      return this.normalizeString(value1) === this.normalizeString(value2);
    }
    
    return value1 === value2;
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
      }
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
      accuracy: 0
    };

    if (modelResult?.error) {
      comparison.error = modelResult.error;
      return comparison;
    }

    this.deepCompare(modelResult, truthResult, comparison, '');

    if (comparison.totalFields > 0) {
      comparison.accuracy = (comparison.matchingFields / comparison.totalFields) * 100;
    }

    return comparison;
  }

  static deepCompare(obj1, obj2, comparison, prefix) {
    for (const key in obj2) {
      const fullKey = prefix ? `${prefix}.${key}` : key;
      comparison.totalFields++;

      if (typeof obj2[key] === 'object' && obj2[key] !== null && !Array.isArray(obj2[key])) {
        if (obj1[key] && typeof obj1[key] === 'object') {
          this.deepCompare(obj1[key], obj2[key], comparison, fullKey);
        } else {
          comparison.missingFields.push(fullKey);
        }
      } else {
        // Use the new normalized comparison
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

    for (const filePath of pdfFiles.slice(0, 5)) {
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