prompts = {
    'supplier':'''
    I want you to process the document with high accuracy to generate the following fields and return a json document with filled information 
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
    "tcsAmount": ""
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
  "IRN_Number":""
}

  NOTE : If the image is blurry or some information is missing then leave that part as empty string and highlight what parts are missing and why''',

    'transporter':''' 
    I want you to process the document with high accuracy to generate the following fields and return a json document with filled information 


    {
  "transporterBill": {
    "invoiceNumber": "",
    "lrNumber": "",
    "vehicleNumber": "",
    "date": "",
    "amount": ""
  }
}
    
  NOTE : If the image is blurry or some information is missing then leave that part as empty string and highlight what parts are missing and why
     '''
}