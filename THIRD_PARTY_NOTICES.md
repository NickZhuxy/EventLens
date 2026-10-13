# Third-party notices

EventLens owner and maintainer: Xiangyi (Nick) Zhu.

- Python and its standard library are used under the Python Software Foundation license and associated notices: https://docs.python.org/3/license.html . No Python distribution is bundled with this source project.
- setuptools 80.9.0 is used only to build/install the package. Its source license is MIT: https://github.com/pypa/setuptools/blob/v80.9.0/LICENSE . No setuptools source is copied into this project.
- The optional service uses FastAPI, Uvicorn, Pydantic, Starlette, and their dependencies. Versions are recorded in `deploy/requirements.lock`. The Docker image installs these distributions with their package notices and uses the official Python base image pinned in `Dockerfile`.
- Adobe, Salesforce and Autodesk disclosures remain the property of their respective issuers. Source text, issuer copyright/trademark notices, URLs, retrieval timestamps and normalization notes are retained with the snapshots/captures. Public accessibility is not an assertion of a redistribution license.
- SEC EDGAR hosts issuer exhibits; that hosting does not turn issuer-owned materials into EventLens-authored content.
- The macro corpus reproduces Federal Reserve Board statements and meeting minutes from their public official pages. Publisher attribution, URLs, dates, reader captures, and hashes are retained. EventLens did not author those documents. See docs/macro_data_provenance.md for the capture method and limitations.
- Runtime calendar collection reads official ECB, USDA, CFTC, NBS, New York Fed, and BLS pages. Each saved version retains its publisher, URL, normalized calendar text, capture, and hashes. These publisher materials are not EventLens-authored text; private runtime captures are not bundled in the repository. The event catalog contains independently written descriptions and public reference links.
- The OpenAI Chat Completions API reference informed the optional HTTP request structure: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create . No OpenAI SDK or API key is bundled.

No open-source license for the owner's original project code has been selected. The repository is private. The public availability of cited material is not an assertion of a blanket redistribution license.
