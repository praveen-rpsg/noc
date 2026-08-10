import React, { useState } from 'react';

export default function FirmwareUpgrade() {
    const [file, setFile] = useState(null);
    const [targetIps, setTargetIps] = useState('');
    const [vendor, setVendor] = useState('');
    const [tftpIp, setTftpIp] = useState('192.168.65.1'); // Default Docker Gateway or Host IP
    const [status, setStatus] = useState('');

    const handleUpload = async (e) => {
        e.preventDefault();
        if (!file) return alert("Please select a firmware image.");

        const formData = new FormData();
        formData.append('file', file);
        formData.append('tftp_server_ip', tftpIp);
        if (targetIps) formData.append('target_ips', targetIps);
        if (vendor) formData.append('vendor_filter', vendor);

        setStatus('Uploading file and initiating job...');

        try {
            const response = await fetch('/api/firmware/upload', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            setStatus(data.message || data.error);
        } catch (error) {
            setStatus('Upload failed: ' + error.message);
        }
    };

    return (
        <div className="p-6 bg-white rounded-lg shadow-md">
            <h2 className="text-xl font-bold mb-4">Bulk OS / Firmware Upgrade</h2>
            <form onSubmit={handleUpload} className="space-y-4">
                
                {/* File Browser */}
                <div>
                    <label className="block text-sm font-medium text-gray-700">OS Image File (.bin, .tar)</label>
                    <input 
                        type="file" 
                        onChange={(e) => setFile(e.target.files[0])} 
                        className="mt-1 block w-full border border-gray-300 rounded-md p-2"
                        required
                    />
                </div>

                {/* Target Selection */}
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Filter by Vendor/Model</label>
                        <select 
                            value={vendor} 
                            onChange={(e) => setVendor(e.target.value)}
                            className="mt-1 block w-full border border-gray-300 rounded-md p-2"
                        >
                            <option value="">All Vendors</option>
                            <option value="cisco_ios">Cisco IOS</option>
                            <option value="cisco_nxos">Cisco NX-OS</option>
                            <option value="fortinet">Fortinet</option>
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700">Specific IPs (Comma-separated)</label>
                        <input 
                            type="text" 
                            placeholder="192.168.1.1, 192.168.1.2" 
                            value={targetIps} 
                            onChange={(e) => setTargetIps(e.target.value)}
                            className="mt-1 block w-full border border-gray-300 rounded-md p-2"
                        />
                    </div>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700">TFTP Server IP (Your Backend IP)</label>
                    <input 
                        type="text" 
                        value={tftpIp} 
                        onChange={(e) => setTftpIp(e.target.value)}
                        className="mt-1 block w-full border border-gray-300 rounded-md p-2"
                        required
                    />
                </div>

                <button 
                    type="submit" 
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
                >
                    Push Firmware
                </button>
            </form>
            
            {status && (
                <div className="mt-4 p-4 bg-gray-100 rounded-md text-sm text-gray-800">
                    {status}
                </div>
            )}
        </div>
    );
}