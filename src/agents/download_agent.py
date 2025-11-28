"""
Download agent for capturing offer letters.

This agent executes download workflows defined in school configs.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import asyncio

from src.models.config_schemas import SchoolConfigV2, ActionContext, ActionType
from src.automation.playwright_manager import PlaywrightManager
from src.agents.vision_agent import VisionAgent
from src.agents.action_executor import ActionExecutor
from src.utils.storage import storage
from src.utils.logger import log


class DownloadAgent:
    """Specialized agent for downloading offer letters"""
    
    def __init__(self, browser: PlaywrightManager, vision_agent: VisionAgent):
        self.browser = browser
        self.vision_agent = vision_agent
        self.executor = ActionExecutor(browser, vision_agent)
    
    async def download_offer(
        self,
        config: SchoolConfigV2,
        application_id: str,
        max_retries: Optional[int] = None
    ) -> Optional[Path]:
        """
        Download offer letter using the configured workflow.
        
        Args:
            config: School configuration with download workflow
            application_id: Application ID for naming the downloaded file
            max_retries: Override config's max_retries
        
        Returns:
            Path to saved offer file, or None if download failed
        """
        retries = max_retries if max_retries is not None else config.download.max_retries
        
        for attempt in range(1, retries + 1):
            try:
                log.info(f"=== Download Attempt {attempt}/{retries} ===")
                
                # Create context
                context = ActionContext(
                    application_id=application_id,
                    school_name=config.school_name
                )
                
                # Execute each step in the download workflow
                download_result = None
                
                for i, step in enumerate(config.download.steps, 1):
                    log.info(f"Download step {i}/{len(config.download.steps)}: {step.action.value}")
                    
                    # Special handling for download capture
                    if step.action == ActionType.CAPTURE_DOWNLOAD:
                        # Previous step should have triggered the download
                        result = await self.executor.execute_action(step, context)
                        
                        if result["success"] and "data" in result:
                            download_result = result["data"]  # This is the temp file path
                            log.info(f"✓ Download captured: {download_result}")
                        else:
                            log.warning("Download capture step did not return file path")
                    
                    # For find_and_click with triggers_download=True
                    elif step.action == ActionType.FIND_AND_CLICK and step.triggers_download:
                        # Track pages before click to detect new ones
                        pages_before = len(self.browser.context.pages)
                        current_page = self.browser.page
                        
                        # Set up download listener before clicking
                        try:
                            # Use longer timeout for async downloads (modal/spinner pattern)
                            download_timeout = max(step.timeout * 1000, 30000)  # At least 30 seconds
                            log.info(f"Setting up download listener with {download_timeout}ms timeout...")
                            
                            async with self.browser.page.expect_download(timeout=download_timeout) as download_info:
                                # Execute the click
                                result = await self.executor.execute_action(step, context)
                                # Wait extra time for modal/spinner to process
                                log.info("Waiting for download to start (modal/spinner may appear)...")
                                await self.browser.wait(5)
                            
                            # Capture the download
                            download = await download_info.value
                            log.info(f"✓ Download triggered: {download.suggested_filename}")
                            
                            # Save to temp
                            temp_path = Path(f"/tmp/{download.suggested_filename}")
                            await download.save_as(temp_path)
                            download_result = temp_path
                            
                        except Exception as e:
                            log.warning(f"Direct download failed: {e}")
                            
                            # Wait a bit more and try to capture download again
                            log.info("Waiting longer for async download...")
                            await self.browser.wait(5)
                            
                            # Try a second time with expect_download
                            try:
                                async with self.browser.page.expect_download(timeout=10000) as download_info:
                                    await self.browser.wait(2)
                                
                                download = await download_info.value
                                log.info(f"✓ Download captured on retry: {download.suggested_filename}")
                                
                                temp_path = Path(f"/tmp/{download.suggested_filename}")
                                await download.save_as(temp_path)
                                download_result = temp_path
                            
                            except Exception as retry_error:
                                log.warning(f"Retry download capture failed: {retry_error}")
                                
                                # Check for NEW tabs/popups (not existing ones)
                                all_pages = self.browser.context.pages
                                
                                if len(all_pages) > pages_before:
                                    # Get the actually new page (not an existing one)
                                    for page in all_pages:
                                        if page != current_page and page.url != current_page.url:
                                            log.info(f"New page detected: {page.url}")
                                            
                                            # Try to download PDF from new page
                                            if 'pdf' in page.url.lower() or 'binary-documents' in page.url or 'inline=true' in page.url:
                                                log.info("PDF URL detected in new page")
                                                
                                                try:
                                                    # Use fetch API to download
                                                    pdf_bytes = await page.evaluate("""
                                                        async (url) => {
                                                            const response = await fetch(url);
                                                            const blob = await response.blob();
                                                            const buffer = await blob.arrayBuffer();
                                                            return Array.from(new Uint8Array(buffer));
                                                        }
                                                    """, page.url)
                                                    
                                                    pdf_bytes = bytes(pdf_bytes)
                                                    log.info(f"✓ Downloaded PDF via fetch: {len(pdf_bytes)} bytes")
                                                    
                                                    # Save to temp file
                                                    temp_path = Path(f"/tmp/{application_id}_offer.pdf")
                                                    temp_path.write_bytes(pdf_bytes)
                                                    download_result = temp_path
                                                    
                                                    await page.close()
                                                
                                                except Exception as pdf_error:
                                                    log.error(f"PDF download from new page failed: {pdf_error}")
                                                    if page and not page.is_closed():
                                                        await page.close()
                                            break
                    
                    # For find_and_click with opens_new_tab=True (OCAS case)
                    elif step.action == ActionType.FIND_AND_CLICK and step.opens_new_tab:
                        # Execute the click (ActionExecutor handles popup detection)
                        result = await self.executor.execute_action(step, context)
                        
                        # Check if a new page was opened
                        await self.browser.wait(2)
                        all_pages = self.browser.context.pages
                        
                        if len(all_pages) > 1:
                            new_page = all_pages[-1]
                            log.info(f"✓ New page opened: {new_page.url}")
                            
                            # Check if it's a PDF URL
                            if 'pdf' in new_page.url.lower() or 'binary-documents' in new_page.url or 'inline=true' in new_page.url:
                                log.info("PDF URL detected - downloading content...")
                                
                                try:
                                    # Use fetch API to download actual PDF bytes
                                    pdf_bytes = await new_page.evaluate("""
                                        async (url) => {
                                            const response = await fetch(url);
                                            const blob = await response.blob();
                                            const buffer = await blob.arrayBuffer();
                                            return Array.from(new Uint8Array(buffer));
                                        }
                                    """, new_page.url)
                                    
                                    pdf_bytes = bytes(pdf_bytes)
                                    log.info(f"✓ Downloaded PDF via fetch API: {len(pdf_bytes)} bytes")
                                    
                                    # Save to temp file
                                    temp_path = Path(f"/tmp/{application_id}_offer.pdf")
                                    temp_path.write_bytes(pdf_bytes)
                                    download_result = temp_path
                                    
                                    await new_page.close()
                                    log.info("✓ PDF downloaded and new tab closed")
                                    
                                except Exception as pdf_error:
                                    log.error(f"PDF download from popup failed: {pdf_error}")
                                    import traceback
                                    log.error(traceback.format_exc())
                                    if new_page and not new_page.is_closed():
                                        await new_page.close()
                    else:
                        # Regular step
                        result = await self.executor.execute_action(step, context)
                        
                        if not result["success"]:
                            if step.optional:
                                log.warning(f"Optional step failed, continuing...")
                                continue
                            else:
                                log.error(f"Required step failed: {step.action.value}")
                                raise Exception(f"Download step {i} failed")
                    
                    # Small delay between steps
                    await self.browser.wait(1)
                
                # Save the downloaded file using storage manager
                if download_result and download_result.exists():
                    file_bytes = download_result.read_bytes()
                    log.info(f"File size: {len(file_bytes)} bytes")
                    
                    # Determine extension
                    extension = download_result.suffix.lstrip('.')
                    if not extension:
                        extension = 'pdf'
                    
                    # Save using storage manager
                    saved_path = storage.save_offer(
                        school_name=config.school_name,
                        application_id=application_id,
                        file_content=file_bytes,
                        extension=extension
                    )
                    
                    # Clean up temp file
                    try:
                        download_result.unlink()
                    except:
                        pass
                    
                    log.info(f"✓ Offer saved to: {saved_path}")
                    return saved_path
                else:
                    log.warning("No file was downloaded")
                    raise Exception("Download completed but no file captured")
            
            except Exception as e:
                log.error(f"Download attempt {attempt} failed: {e}")
                
                if attempt < retries:
                    log.info(f"Retrying in {config.download.retry_delay} seconds...")
                    await asyncio.sleep(config.download.retry_delay)
                else:
                    log.error(f"All {retries} download attempts failed")
                    return None
        
        return None

