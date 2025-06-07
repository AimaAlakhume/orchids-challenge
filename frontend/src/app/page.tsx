"use client"
import React, { useState } from "react";
import axios from "axios";
import { saveAs } from 'file-saver';

interface ScrapedContent {
  url: string;
  title: string;
  html_content_length: number;
  screenshot_url?: string;
  assets_count?: {
    images: number;
    stylesheets: number;
    scripts: number;
    links: number;
  };
  id: string;
}

interface CloneResponse {
  success: boolean;
  cloned_html?: string;
  message?: string;
}

export default function Home() {
  
  const apiUrl = 'http://127.0.0.1:8000';
  const [url, setUrl] = useState("");
  const [clonedHtml, setClonedHtml] = useState<string | null>(null);
  const [websiteTitle, setWebsiteTitle] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateUrl = (url: string) => {
    try {
      new URL(url);
      return true;
    }
    catch {
      return false;
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setClonedHtml(null);
    setWebsiteTitle(null);
    setError(null);

    if (!validateUrl(url)) {
      alert("Please enter a valid URL.");
      return;
    }

    setLoading(true);
    try {
      const scrapeRes = await axios.post<ScrapedContent>(`${apiUrl}/webscrape`, { url: url });
      console.log('Scraped content: ', scrapeRes.data);
      setWebsiteTitle(scrapeRes.data.title);
      
      const cloneRes = await axios.post<CloneResponse>(`${apiUrl}/clone-website`, { url_id: scrapeRes.data.id });
      console.log('Cloned content: ', cloneRes.data);
      
      if (cloneRes.data.success && cloneRes.data.cloned_html) {
        setClonedHtml(cloneRes.data.cloned_html);
      } else {
        setError(cloneRes.data.message || "LLM cloning failed for an unknown reason.");
      }
    } catch (err: any) {
      console.error("Error:", err);
      if (axios.isAxiosError(err) && err.response) {
        setError(`Error: ${err.response.status} - ${err.response.data.detail || err.message}`);
      } else {
        setError(`An unexpected error occurred: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  }

  const handleDownloadHtml = () => {
    if (clonedHtml) {
      const blob = new Blob([clonedHtml], { type: "text/html;charset=utf-8" });
      saveAs(blob, "cloned_website.html");
    }
  }

  return (
    <div className="min-h-screen flex flex-col justify-center items-center bg-gray-100 p-4">
      <div className="max-w-md w-full bg-white shadow-lg rounded-lg p-8">
        <h1 className="text-2xl font-bold mb-6 text-center text-gray-800">Website Cloner</h1>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="website-url" className="block text-gray-700 text-sm font-semibold mb-2">
              Enter Website URL
            </label>
            <input
              id="website-url"
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="shadow-sm appearance-none border border-gray-300 rounded w-full py-3 px-4 text-gray-700 leading-tight focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="https://example-site.com"
              disabled={loading}
            />
          </div>
          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-md focus:outline-none focus:shadow-outline transition duration-150 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading}
          >
            {loading ? "Scraping & Cloning..." : "Clone Website"}
          </button>
        </form>

        {error && (
          <div className="mt-6 p-3 bg-red-100 border border-red-400 text-red-700 rounded-md">
            <p className="font-bold">Error:</p>
            <p className="text-sm">{error}</p>
          </div>
        )}
      </div>

      {clonedHtml && (
        <div className="mt-8 max-w-6xl w-full bg-white shadow-lg rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800 text-center">{websiteTitle && ` (${websiteTitle})`} Website Cloned</h2>
          <p className="text-sm text-gray-600 mb-4 text-center">
            A preview of the {websiteTitle && ` (${websiteTitle})`} website, recreated by Claude 4 Sonnet.
          </p>
          <div className="border border-gray-300 rounded-md overflow-hidden mb-4" style={{ height: '600px', width: '100%' }}>
            <iframe
              srcDoc={clonedHtml}
              title="Cloned Website Preview"
              className="w-full h-full border-0"
              sandbox="allow-same-origin allow-scripts"
            ></iframe>
          </div>
          <button
            onClick={handleDownloadHtml}
            className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-md focus:outline-none focus:shadow-outline transition duration-150 ease-in-out"
          >
            Download HTML File
          </button>
        </div>
      )}
    </div>
  )
}