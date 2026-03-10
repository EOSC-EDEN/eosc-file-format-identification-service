# File Format Identification Service (FFIS) Specification

**Version:** 0.1.0 (Draft)
**Date:** 2026-03-10
**Status:** Proposed specification for the EOSC EDEN architecture, open for review by EDEN technical working groups.

## Abstract

This specification defines the functional and technical requirements for a File Format Identification Service (FFIS) within the EOSC EDEN ecosystem. The FFIS is responsible for analyzing ingested byte streams to determine their technical format, version, and profile. By mapping files to standardized registries (such as PRONOM), this service enables Trusted Digital Archives (TDA) to assign preservation strategies, verify technical consistency against user assumptions, and ensure the long-term interoperability of research data.

## Rationale

Digital archives cannot reliably migrate, render, or emulate files without knowing their format. File extensions and user-supplied MIME types are unreliable. This service performs identification against binary signatures and maps results to standardised registries (PRONOM, MIME, Wikidata), providing the prerequisite input for preservation planning, format migration, and ingest verification. There are many existing tools for this, however no centralized orchestrator service seems to exist.

## Introduction

In the context of a Trusted Digital Archive (TDA), file extensions are unreliable indicators of file content. Without accurate technical identification, digital objects are effectively opaque byte streams that cannot be reliably rendered, migrated, or emulated over time.

The File Format Identification Service is a fundamental component of the preservation workflow. It serves two critical purposes:

1. **Preservation Planning:** It provides the granularity (versions/profiles) needed to select appropriate preservation actions (e.g., migrating a Word 97 file to PDF/A).
2. **Ingest Verification:** It validates that the technical reality of a file matches the metadata provided by the depositor, ensuring data quality at the point of entry.

This service can be utilized at the "Ingest" phase of the OAIS model. The output of this service is a prerequisite for the "Preservation Planning" entity to function. For example, the preservation system cannot decide to trigger a "Migrate to Open Standard" workflow if it does not first know that the incoming file is `fmt/40` (Microsoft Word 97).

## Scope

### In scope

* **Identification methodology:** Identification of file formats based on internal binary signatures (magic numbers) and structural analysis (e.g., offset signatures and XML structure).
* **Container-based formats:** Structural analysis of container formats (e.g., ZIP, OLE2, TAR) to distinguish specific application formats (e.g., .docx, .epub, .apk) from generic archive files. The service MUST parse container structures (like ZIP or OLE2) to identify if the file is a specific format (e.g., distinguishing a .docx or .epub from a generic .zip). If a container does not match a specific application profile, it MUST be identified by its generic format (e.g., x-fmt/263 for ZIP). Container identification SHOULD inspect container metadata (e.g., ZIP central directory records) rather than extracting the full archive contents, as archives in domains such as bioinformatics and life sciences can be very large.
* **Bulk analysis** of multiple local files.
* **Granular identification** of specific format versions (e.g., PDF 1.7) and profiles (e.g., PDF/A-1b).
* **Orchestration** of multiple identification tools to maximize coverage and accuracy.
* **Mapping:** Identified formats mapping to unique identifiers from external registries (PRONOM PUID, MIME type, Wikidata, Library of Congress FDD identifiers, etc.).
* **Reporting** of identification results in a machine-actionable format.
* **User-facing UI**, where the same functionality as the API can be accessed.
* **Deployment Model:** The service specification is deployment-agnostic to support different TDA infrastructures. It acts as a functional component that:
    * MUST be deployable locally (e.g., via Container/Docker) for TDAs requiring strict data sovereignty or high-performance local processing.
    * MAY be deployed as a centralized/SaaS solution for smaller TDAs with lower volume or less technical infrastructure.

### Out of scope

* **Validation:** Detailed conformance checking (ensuring a file complies strictly with its format specification) is a separate service, though it relies on identification.
* **Characterization:** The extraction of descriptive technical metadata (e.g., sampling rate, color space, camera model) is distinct from the identification of the format itself, except where such properties define a specific format profile (e.g., PDF/A).
    * A technical property is considered "Characterization" (out of scope) unless its presence results in a distinct identifier (e.g., PUID) within the reference registry (PRONOM). For example, while "Encryption" might be a metadata property for some formats, if PRONOM assigns a specific PUID to "Encrypted PDF" (e.g., fmt/754), detecting it becomes a matter of Identification (in scope).
* **Fixity:** Checksum calculation is assumed to be handled by the storage layer or a separate microservice.
* **Content-policy compliance:** Indication of whether a file follows the content-policy of the submitter.
* **Recursive content analysis (extraction):** The service identifies the digital object as provided. It does not automatically extract or identify individual files contained within archive formats (e.g., ZIP, TAR, ISO) unless those files constitute a specific format profile (as per "Container-based formats" in scope). Note that some identification tools (e.g., DROID) support configurable recursive inspection of archive contents; exposing such settings is an implementation concern and not mandated by this specification.
* **Registry contribution:** Curating or submitting new file format signatures to external registries (e.g., PRONOM, Apache Tika) is not the responsibility of the FFIS. However, the service should facilitate such contributions by supporting export of unidentified format reports (see Requirement Group 3 and Non-normative Guidance). Coordination of registry contributions is expected to be handled by the relevant EDEN work packages (e.g., WP1 for registry liaison, WP3 for collecting domain-specific format requirements).

## Core Preservation Processes

The core preservation processes describe which inputs are required and which outputs are expected for a successful execution of the processes. Based on the description for [CPP-008 - File Format Identification][cpp-008], the expected input for this process would be the file(s) that need to be identified. Based on the output described in the CPP description, the output must include the following properties:

* **Technical metadata:**
    * Format identifier(s)
    * Accompanied by registry identifier
* **Provenance metadata:**
    * Date (of identification)
    * Outcome (success or failure):
        * *Success:* file format was identified in all registries
        * *Warning / partial success:* file format has matches in some registries, but not in others
        * *Failure:* file format was not identified in any registry
    * Tool used for identification (including version, output, identification methods, code repository)

## Conformance

The keywords MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## Normative Requirements

### Requirement Group 1 – Identification Methodology

* **{{ FFIS-REQ-1-01 }}** The Service MUST identify file formats based on the file's internal technical structure and binary signatures (magic numbers). (CPP-008)
* **{{ FFIS-REQ-1-02 }}** The Service MUST NOT rely solely on file extensions or user-provided MIME types for identification, as these are considered unreliable.
    * E.g., on a web server, a MIME type is typically defined by the host of the file, and may contain things like `application/xyz` (no validation is mandatory) which does not provide useful information.
* **{{ FFIS-REQ-1-03 }}** The Service MUST identify formats to the highest possible level of granularity, including specific versions (e.g., TIFF 6.0) and profiles (e.g., GeoTIFF) where distinguishable.
* **{{ FFIS-REQ-1-04 }}** The Service SHOULD integrate multiple distinct identification engines (e.g., Siegfried, DROID, Apache Tika) to ensure broad coverage of legacy, scientific, and proprietary formats. (CPP-008)
* **{{ FFIS-REQ-1-05 }}** The Service MAY allow the caller to specify which identification methods or engines to apply for a given request (e.g., binary signature only, container analysis only). When no preference is specified, the Service MUST apply its default set of identification methods.

### Requirement Group 2 – Registry and Standardization

* **{{ FFIS-REQ-2-01 }}** The Service MUST map identified formats to one or more persistent unique identifiers from recognized external registries.
    * Each reported identifier MUST include both the Value (e.g., `fmt/412`) and the Registry/Scheme name (e.g., PRONOM).
    * The Service SHOULD include a persistent URI for the identified format or the registry entry (e.g., `https://www.nationalarchives.gov.uk/pronom/fmt/412`) where available.
    * The PRONOM Unique Identifier (PUID) is the recommended primary identifier.
    * If the Service operates offline or cannot reach an external registry, it SHOULD still attempt identification using locally available signature databases. Where a format can be identified by an integrated tool but no persistent registry identifier can be assigned, the result MUST indicate this partial state (see CPP outcome "Warning / partial success").
* **{{ FFIS-REQ-2-02 }}** The Service MUST report the Internet Media Type (MIME type) for identified files to ensure compatibility with web-based access systems.
* **{{ FFIS-REQ-2-03 }}** The Service output MUST be machine-actionable (e.g., JSON, XML) to facilitate automated preservation workflows and reporting. Identifiers MUST be structured in a way that separates the Value, Scheme, and (optionally) URI into distinct fields to allow for easy parsing.

### Requirement Group 3 – Reporting and Conflict Resolution

* **{{ FFIS-REQ-3-01 }}** The Service MUST report the "Basis of Identification" (e.g., identified via byte signature, container parsing, or AI-assisted pattern matching).
* **{{ FFIS-REQ-3-02 }}** The Service MUST provide full provenance for the identification process:
    * The output MUST include a list of all tools/registries utilized and their individual raw results, regardless of whether they agree or conflict.
* **{{ FFIS-REQ-3-03 }}** Where multiple tools produce conflicting results, the Service MUST apply deterministic logic to select the primary identification.
    * Implementers should define a hierarchy (e.g., PRONOM > Wikidata > MIME). A specific signature match (PUID) SHOULD overrule a probabilistic match or a generic media type.
* **{{ FFIS-REQ-3-04 }}** The Service MUST generate a warning or error flag if the identified format differs significantly from the file extension or any user-supplied format metadata (if provided), provided that the reference registry (such as PRONOM or Unix file) defines valid extensions for the identified format.
* **{{ FFIS-REQ-3-05 }}** The Service MUST flag files that cannot be matched to any registry entry as "unidentified" and classify them as high preservation risk.
* **{{ FFIS-REQ-3-06 }}** The Service SHOULD support export of unidentified format reports in a structured, machine-actionable format to facilitate submission to external registries (e.g., PRONOM, Apache Tika). The export SHOULD include the file's binary signature characteristics, size, and any partial identification results.

### Requirement Group 4 – Integration and Interface

* **{{ FFIS-REQ-4-01 }}** The Service API MUST support two modes of input to facilitate different deployment models:
    * **By Value (Byte Stream):** Accepting file content directly via the API (e.g., HTTP POST upload). This supports the SaaS/Centralized use case.
    * **By Reference (File URI/Path):** Accepting a pointer to a file accessible to the service (e.g., `file:///mnt/data/obj.pdf`). This supports the Local/Containerized use case, enabling "Zero-Copy" chaining with other preservation services without redundant network transfer.
* **{{ FFIS-REQ-4-02 }}** The Service SHALL provide a user interface so that humans with less technical knowledge can interact via a browser.

### Requirement Group 5 – Security

* **{{ FFIS-REQ-5-01 }}** The Service SHOULD implement authentication and authorization.
* **{{ FFIS-REQ-5-02 }}** Transfer of data to and from the Service SHOULD be encrypted in transit (e.g., HTTPS / TLS 1.2 or higher).
* **{{ FFIS-REQ-5-03 }}** The Service MUST enforce upload size limits and publish those limits.
* **{{ FFIS-REQ-5-04 }}** The Service MUST implement protection against malicious input such as zip bombs (e.g., decompression ratio checks, recursion depth limits).
* **{{ FFIS-REQ-5-05 }}** The Service SHOULD sanitize and validate all file paths when operating in "By Reference" mode to prevent path traversal attacks.

### Requirement Group 6 – Deployment

* **{{ FFIS-REQ-6-01 }}** The Service MUST be deployable locally (e.g., via Container/Docker).
* **{{ FFIS-REQ-6-02 }}** The Service MAY be deployed as a centralized/SaaS solution.

## Non-normative Guidance

### Implementation Considerations

* **Tooling:** It is highly recommended to use Siegfried as the primary engine due to its performance and frequent updates via the PRONOM registry. Secondary tools can be used to augment coverage for scientific or rich-media formats:
    * Apache Tika
    * FileType (<https://github.com/theseus-rs/file-type>)
    * Linux `file` command
    * Google Magika (<https://github.com/google/magika>)
    * JSONID (<https://pypi.org/project/jsonid/>)
    * GitHub Linguist

* **Internal Orchestration Strategies:** The implementation should provide chaining logic to optimize performance and accuracy:
    * *Hierarchical refinement:* If the primary engine identifies a file broadly as `text/plain` or `application/json`, the service should verify if a specialized tool can provide a more granular identification:
        * GitHub Linguist for source code
        * JSONID for specific JSON schemas
    * *Format-specific routing:* Executables or binaries that fail standard identification should be routed to Google Magika for AI-assisted identification.
    * *Resolving tool conflicts:* When resolving tool conflicts, implementers should define a Registry Hierarchy. Example: PRONOM > Wikidata > MIME. This provides a deterministic outcome when different tools provide identifiers from different registries.

* **Input Metadata:** Providing format metadata (like a claimed MIME type) should be optional in the API. The service is designed to identify files "blindly"; the comparison logic is an auxiliary verification step used only when the calling system provides an assertion to test against.

* **Performance:** For high-throughput environments like EOSC, the service should cache identification results based on file checksums (hashes) to avoid re-processing identical files.

* **Conflict Resolution Logic:** When orchestrating multiple tools, the service should resolve conflicts to provide a "primary" identification for the TDA. Recommended strategies include:
    * *Specificity/Granularity:* Prefer `fmt/40` (Word 97) over `application/msword`.
    * *Registry hierarchy:* Common example: PRONOM PUID > Library of Congress FDD > Wikidata > MIME type.
    * *Method priority:* A "binary signature" match (high certainty) should generally overrule an "AI/Probabilistic" match.

* **Handling "Unknowns":** If a file cannot be identified (often resulting in `application/octet-stream`), the service should flag this for manual review, as it represents a high preservation risk. Based on the CPP description, part of the output must indicate if the file has been successfully identified. The system should indicate that if the identification fails (referring to the section "Core Preservation Processes"), then a manual review is advised based on the working content-policy.

* **Service Composition and External Orchestration:** To minimize I/O overhead (data gravity) when combining this service with others (e.g., Virus Scanning, Fixity, or Metadata Extraction), it is recommended to use an orchestration pattern:
    * *Shared Volume:* Deploy the FFIS container alongside other analysis containers (like a Virus Scanner) with access to a shared read-only storage volume.
    * *Chaining:* A central workflow engine (e.g., Apache Airflow or a local script) should calculate the file path once and pass that path to each service sequentially using the "By Reference" input mode (FFIS-REQ-4-01).
    * This approach allows multiple distinct services to analyze the same digital object without any redundant network transfer or data duplication.

* **Container Identification Performance:** For container-based identification, implementations should prefer inspecting container metadata (e.g., ZIP central directory, OLE2 directory entries) over full extraction. For example, PRONOM supports container-based identification by reading embedded file entries without extracting the entire archive. This is critical for domains like bioinformatics where compressed archives can be very large. Tools such as DROID that support configurable recursion depth into archives should default to non-recursive mode, with deeper inspection available as an opt-in.

* **Unidentified Format Reporting:** The service should support exporting cases where file formats could not be identified or could not be assigned a persistent unique identifier from registries. This export should be structured in a way that facilitates reporting to registry maintainers (e.g., filing issues on the PRONOM GitHub, contributing signatures to Apache Tika). Contributing to registries is out of scope for the FFIS itself, but the service should facilitate such contributions. In practice, WP3 may collect domain-specific format identification requirements and hand them to WP1 for contribution to registries, as WP1 has existing contacts with the PRONOM team and Tika maintainers.

* **Offline Operation:** The service may be deployed in environments with limited or no internet connectivity (e.g., locally on a laptop). In such scenarios, identification should rely on locally bundled signature databases. Results where a format is recognised by a tool but cannot be mapped to a persistent registry identifier should be clearly flagged as partial identifications rather than failures.

### Example of Structured Identification Output

```json
{
  "identifiers": [
    {
      "value": "fmt/412",
      "scheme": "PRONOM",
      "uri": "https://www.nationalarchives.gov.uk/pronom/fmt/412"
    },
    {
      "value": "image/jpeg",
      "scheme": "MIME"
    }
  ]
}
```

## References

1. EOSC Interoperability Framework: Guidelines for semantic and technical interoperability in the European Open Science Cloud.
2. IETF RFC 2119: Key words for use in RFCs to Indicate Requirement Levels.
3. PRONOM Technical Registry: The National Archives (UK). <https://www.nationalarchives.gov.uk/PRONOM/>
4. ISO 14721:2012: Space data and information transfer systems — Open archival information system (OAIS) — Reference model.
5. Siegfried File Format Identification Service: <https://www.itforarchivists.com/siegfried>
6. EOSC EDEN M1.1 – Report on Identification of Core Preservation Processes. Zenodo. <https://doi.org/10.5281/zenodo.16992452>

[cpp-008]: https://github.com/EOSC-EDEN/wp1-cpp-descriptions/blob/main/CPP-008/EOSC-EDEN_CPP-008_File_Format_Identification.pdf
