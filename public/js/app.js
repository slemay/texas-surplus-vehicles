// Texas Surplus Vehicle Inventory Dashboard Logic
document.addEventListener('DOMContentLoaded', () => {
    let allVehicles = [];

    function formatDriveType(specs, desc) {
        const raw = (specs && specs.DriveType ? specs.DriveType : '').toUpperCase();
        const d = (desc || '').toUpperCase();
        if (raw.includes('FWD') || raw.includes('FRONT')) return 'FWD / Front-Wheel Drive';
        if (raw.includes('AWD') || raw.includes('ALL-WHEEL') || d.includes('AWD')) return 'AWD / All-Wheel Drive';
        if (raw.includes('4WD') || raw.includes('4X4') || d.includes('4X4')) return '4WD / 4x4';
        if (raw.includes('4X2') || raw.includes('RWD') || raw.includes('REAR')) return 'RWD / 4x2';
        if (d.includes('IMPALA')) return 'FWD / Front-Wheel Drive';
        return raw || 'FWD / Front-Wheel Drive';
    }
    
    // DOM Elements
    const vehicleGrid = document.getElementById('vehicle-grid');
    const searchInput = document.getElementById('search-input');
    const makeFilter = document.getElementById('make-filter');
    const bodyFilter = document.getElementById('body-filter');
    const sortSelect = document.getElementById('sort-select');
    const resultsCount = document.getElementById('results-count');
    
    // Stats elements
    const statTotalCount = document.getElementById('stat-total-count');
    const statAvgPrice = document.getElementById('stat-avg-price');
    const statAvgMileage = document.getElementById('stat-avg-mileage');
    const statAvgMpg = document.getElementById('stat-avg-mpg');
    
    // Modal Elements
    const vinModal = document.getElementById('vin-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalTitle = document.getElementById('modal-title');
    const modalAssetNum = document.getElementById('modal-asset-num');
    const modalVinDisplay = document.getElementById('modal-vin-display');
    const modalPrice = document.getElementById('modal-price');
    const modalVehicleImg = document.getElementById('modal-vehicle-img');
    const modalEngine = document.getElementById('modal-engine');
    const modalMpg = document.getElementById('modal-mpg');
    const modalMileage = document.getElementById('modal-mileage');
    const modalDrivetrain = document.getElementById('modal-drivetrain');
    const modalPlant = document.getElementById('modal-plant');
    
    // Recalls Modal Elements
    const recallsHeaderText = document.getElementById('recalls-header-text');
    const recallCountBadge = document.getElementById('recall-count-badge');
    const recallsList = document.getElementById('recalls-list');
    
    const nhtsaTable = document.getElementById('nhtsa-table');
    const copyVinBtn = document.getElementById('copy-vin-btn');
    const refreshDataBtn = document.getElementById('refresh-data-btn');

    let currentSelectedVin = '';

    function decodeDotNetTicks(urlOrTicks) {
        if (!urlOrTicks) return null;
        let ticksStr = String(urlOrTicks).trim().replace(/\/$/, '').split('/').pop();
        if (!/^\d{16,20}$/.test(ticksStr)) {
            const match = String(urlOrTicks).match(/\b(\d{16,20})\b/);
            if (match) ticksStr = match[1];
            else return null;
        }

        try {
            const epochTicks = 621355968000000000n;
            const ticks = BigInt(ticksStr);
            const ms = Number((ticks - epochTicks) / 10000n);
            const date = new Date(ms);

            const formattedCentral = date.toLocaleString('en-US', {
                timeZone: 'America/Chicago',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true,
                timeZoneName: 'short'
            });

            const dateOnly = date.toLocaleDateString('en-US', {
                timeZone: 'America/Chicago',
                month: 'long',
                day: 'numeric',
                year: 'numeric'
            });

            return {
                ticks: ticksStr,
                formattedCentral: formattedCentral,
                dateOnly: dateOnly,
                docUrl: String(urlOrTicks).startsWith('http') ? String(urlOrTicks) : `https://web.tfc.texas.gov/home/showpublisheddocument/232/${ticksStr}`
            };
        } catch (e) {
            console.error('Error decoding .NET Ticks:', e);
            return null;
        }
    }

    function updateTimestampUI(metadata) {
        const defaultTicksUrl = 'https://web.tfc.texas.gov/home/showpublisheddocument/232/639203309514970000';
        let info = null;

        if (metadata && metadata.formattedCentral) {
            info = metadata;
        } else if (metadata && metadata.ticks) {
            info = decodeDotNetTicks(metadata.ticks);
        } else if (metadata && metadata.docUrl) {
            info = decodeDotNetTicks(metadata.docUrl);
        }

        if (!info) {
            info = decodeDotNetTicks(defaultTicksUrl);
        }

        if (info) {
            const bannerTime = document.getElementById('banner-generated-time');
            const headerTime = document.getElementById('header-time-val');
            const ticksVal = document.getElementById('notice-ticks-val');
            const bannerLink = document.getElementById('banner-doc-link');
            const bannerLinkText = document.getElementById('banner-doc-link-text');

            if (bannerTime) bannerTime.textContent = info.formattedCentral;
            if (headerTime) headerTime.textContent = `Generated ${info.formattedCentral}`;
            if (ticksVal) ticksVal.textContent = info.ticks;
            if (bannerLink) bannerLink.href = info.docUrl;
            if (bannerLinkText) bannerLinkText.textContent = info.docUrl;
        }
    }

    // Load initial JSON data
    fetch('data/vehicles_final.json')
        .catch(() => fetch('vehicles_final.json'))
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
            return res.json();
        })
        .then(data => {
            if (Array.isArray(data)) {
                allVehicles = data;
                try { updateTimestampUI(null); } catch (e) { console.error('Timestamp error:', e); }
            } else {
                allVehicles = data.vehicles || [];
                try { updateTimestampUI(data.generatedAt); } catch (e) { console.error('Timestamp error:', e); }
            }
            try { updateStats(allVehicles); } catch (e) { console.error('Stats error:', e); }
            try { renderVehicles(); } catch (e) { console.error('Render error:', e); }
        })
        .catch(err => {
            console.error('Error loading vehicle data:', err);
            if (vehicleGrid) {
                vehicleGrid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: #ef4444; padding: 2rem;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size: 2rem; margin-bottom: 0.5rem;"></i>
                    <p>Failed to load inventory data: ${err.message}</p>
                </div>`;
            }
        });


    function updateStats(vehicles) {
        if (!vehicles || !vehicles.length) return;
        if (statTotalCount) statTotalCount.textContent = vehicles.length;
        
        const totalCost = vehicles.reduce((sum, v) => sum + (v.salesPrice || 0), 0);
        const avgPrice = Math.round(totalCost / vehicles.length);
        if (statAvgPrice) statAvgPrice.textContent = `$${avgPrice.toLocaleString()}`;
        
        const totalMileage = vehicles.reduce((sum, v) => sum + (v.mileage || 0), 0);
        const avgMileage = Math.round(totalMileage / vehicles.length);
        if (statAvgMileage) statAvgMileage.textContent = `${avgMileage.toLocaleString()} mi`;

        const totalMpg = vehicles.reduce((sum, v) => sum + (v.mpg ? v.mpg.combined : 18), 0);
        const avgMpg = (totalMpg / vehicles.length).toFixed(1);
        if (statAvgMpg) statAvgMpg.textContent = `${avgMpg} MPG`;
    }

    function renderVehicles() {
        const searchTerm = searchInput.value.trim().toLowerCase();
        const selectedMake = makeFilter.value;
        const selectedBody = bodyFilter.value;
        const sortVal = sortSelect.value;

        let filtered = allVehicles.filter(v => {
            if (!v) return false;
            const specs = v.specs || {};
            const desc = (v.description || '').toLowerCase();
            const vin = (v.vin || '').toLowerCase();
            const asset = (v.assetNumber || '').toLowerCase();
            const make = (specs.Make || '').toLowerCase();
            const model = (specs.Model || '').toLowerCase();
            const aspiration = (specs.Aspiration || '').toLowerCase();
            
            // Search filter
            const matchesSearch = !searchTerm || desc.includes(searchTerm) || vin.includes(searchTerm) || asset.includes(searchTerm) || make.includes(searchTerm) || model.includes(searchTerm) || aspiration.includes(searchTerm);
            
            // Make filter
            const matchesMake = selectedMake === 'ALL' || (specs.Make || '').toUpperCase().includes(selectedMake);
            
            // Body filter
            let matchesBody = true;
            if (selectedBody === 'SUV') {
                matchesBody = desc.includes('TAHOE') || desc.includes('EXPLORER') || desc.includes('JOURNEY') || (specs.BodyClass || '').includes('SUV');
            } else if (selectedBody === 'Pickup') {
                matchesBody = desc.includes('RAM') || desc.includes('1500') || (specs.BodyClass || '').includes('Pickup');
            } else if (selectedBody === 'Sedan') {
                matchesBody = desc.includes('TAURUS') || desc.includes('IMPALA') || desc.includes('INTERCEPTOR SEDAN') || (specs.BodyClass || '').includes('Sedan');
            }

            return matchesSearch && matchesMake && matchesBody;
        });

        // Sorting
        filtered.sort((a, b) => {
            const specsA = (a && a.specs) || {};
            const specsB = (b && b.specs) || {};
            if (sortVal === 'price-asc') return (a.salesPrice || 0) - (b.salesPrice || 0);
            if (sortVal === 'price-desc') return (b.salesPrice || 0) - (a.salesPrice || 0);
            if (sortVal === 'mpg-desc') return (b.mpg ? b.mpg.combined : 0) - (a.mpg ? a.mpg.combined : 0);
            if (sortVal === 'mileage-asc') return (a.mileage || 0) - (b.mileage || 0);
            if (sortVal === 'year-desc') return (parseInt(specsB.ModelYear) || 0) - (parseInt(specsA.ModelYear) || 0);
            return 0;
        });

        if (resultsCount) resultsCount.textContent = `Showing ${filtered.length} of ${allVehicles.length} vehicles`;

        if (filtered.length === 0) {
            vehicleGrid.innerHTML = `
                <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1rem; color: var(--text-secondary);">
                    <i class="fa-solid fa-car-tunnel" style="font-size: 3rem; margin-bottom: 1rem; color: var(--text-muted);"></i>
                    <h3 style="font-size: 1.2rem; margin-bottom: 0.5rem;">No matching vehicles found</h3>
                    <p style="font-size: 0.9rem;">Try adjusting your search query or filters.</p>
                </div>
            `;
            return;
        }

        vehicleGrid.innerHTML = filtered.map(v => {
            const specs = v.specs || {};
            const displacement = specs.DisplacementL ? `${specs.DisplacementL}L` : '';
            const cyl = specs.EngineCylinders ? `V${specs.EngineCylinders}` : '';
            const drive = formatDriveType(specs, v.description);
            const mpgObj = v.mpg || { city: 16, hwy: 22, combined: 18 };
            const mpgText = `${mpgObj.combined} MPG Est (${mpgObj.city}/${mpgObj.hwy})`;
            const recallCount = v.recalls ? v.recalls.count : 0;
            const isTurbo = (specs.Aspiration || '').toLowerCase().includes('turbo');
            const mileageDisplay = (v.mileage || 0).toLocaleString();
            const priceDisplay = (v.salesPrice || 0).toLocaleString();

            return `
                <div class="vehicle-card" data-vin="${v.vin}">
                    <div class="card-image-wrapper" onclick="openReviewModal('${v.vin}')" title="Click picture for full details">
                        <img src="${v.image}" alt="${v.description}" loading="lazy">
                        <span class="price-chip">$${priceDisplay}</span>
                        <span class="asset-chip"># ${v.assetNumber}</span>
                    </div>
                    <div class="card-content">
                        <h3 class="card-title">${v.description}</h3>
                        <p class="card-subtitle"><i class="fa-solid fa-barcode"></i> VIN: ${v.vin}</p>
                        
                        <div class="card-specs-pill-container">
                            <span class="spec-pill mpg-pill"><i class="fa-solid fa-leaf"></i> ${mpgText}</span>
                            <span class="spec-pill recall-pill"><i class="fa-solid fa-triangle-exclamation"></i> ${recallCount} Recalls</span>
                            ${displacement || cyl ? `<span class="spec-pill"><i class="fa-solid fa-microchip"></i> ${displacement} ${cyl}</span>` : ''}
                            ${isTurbo ? `<span class="spec-pill text-amber"><i class="fa-solid fa-bolt"></i> Turbocharged</span>` : ''}
                            <span class="spec-pill"><i class="fa-solid fa-gears"></i> ${drive}</span>
                        </div>

                        <div class="card-footer">
                            <span class="mileage-text">
                                <i class="fa-solid fa-gauge-simple-high"></i> ${mileageDisplay} miles
                            </span>
                            <button class="btn btn-outline view-details-btn" onclick="openVinModal('${v.vin}')">
                                View Specs <i class="fa-solid fa-chevron-right"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Expert Review Modal Elements
    const reviewModal = document.getElementById('review-modal');
    const reviewModalCloseBtn = document.getElementById('review-modal-close-btn');
    const reviewCloseFooterBtn = document.getElementById('review-close-footer-btn');
    const reviewSwitchToSpecsBtn = document.getElementById('review-switch-to-specs-btn');
    const viewFullReviewBtn = document.getElementById('view-full-review-btn');

    const reviewModalTitle = document.getElementById('review-modal-title');
    const reviewModalSubtitle = document.getElementById('review-modal-subtitle');
    const reviewRatingText = document.getElementById('review-rating-text');
    const reviewStars = document.getElementById('review-stars');
    const reviewSummaryText = document.getElementById('review-summary-text');
    const reviewProsList = document.getElementById('review-pros-list');
    const reviewConsList = document.getElementById('review-cons-list');
    const reviewVerdictText = document.getElementById('review-verdict-text');
    const reviewEdmundsLink = document.getElementById('review-edmunds-link');

    const kbbSavingsPill = document.getElementById('kbb-savings-pill');
    const kbbSurplusPrice = document.getElementById('kbb-surplus-price');
    const kbbFairPrice = document.getElementById('kbb-fair-price');
    const kbbRangeMin = document.getElementById('kbb-range-min');
    const kbbRangeMax = document.getElementById('kbb-range-max');
    const kbbRangeBarFill = document.getElementById('kbb-range-bar-fill');
    const kbbPriceRange = document.getElementById('kbb-price-range');
    const kbbRetailVal = document.getElementById('kbb-retail-val');
    const kbbTotalSavings = document.getElementById('kbb-total-savings');
    const kbbOfficialLink = document.getElementById('kbb-official-link');

    // Specs Modal Elements for Review Preview
    const specsEdmundsRating = document.getElementById('specs-edmunds-rating');
    const specsEdmundsSummary = document.getElementById('specs-edmunds-summary');
    const specsKbbFair = document.getElementById('specs-kbb-fair');
    const specsKbbSavings = document.getElementById('specs-kbb-savings');

    // Open Expert Review Modal
    window.openReviewModal = function(vin) {
        const v = allVehicles.find(x => x.vin === vin);
        if (!v) return;

        currentSelectedVin = v.vin;
        vinModal.classList.remove('active');

        reviewModalTitle.textContent = v.description;
        reviewModalSubtitle.innerHTML = `Asset #${v.assetNumber} &bull; VIN: ${v.vin}`;

        // Edmunds Review Population
        const edmunds = v.edmundsReview || {};
        reviewRatingText.textContent = edmunds.ratingText || `Edmunds Rating: ${edmunds.rating || 4.5} / 5`;
        
        // Stars HTML
        const ratingNum = edmunds.rating || 4.5;
        let starsHTML = '';
        for (let i = 1; i <= 5; i++) {
            if (i <= Math.floor(ratingNum)) {
                starsHTML += '<i class="fa-solid fa-star text-gold"></i>';
            } else if (i - ratingNum < 1) {
                starsHTML += '<i class="fa-solid fa-star-half-stroke text-gold"></i>';
            } else {
                starsHTML += '<i class="fa-regular fa-star text-muted"></i>';
            }
        }
        reviewStars.innerHTML = starsHTML;

        reviewSummaryText.textContent = edmunds.summary || 'Comprehensive Edmunds vehicle overview for this model.';
        
        if (edmunds.pros && edmunds.pros.length) {
            reviewProsList.innerHTML = edmunds.pros.map(p => `<li><i class="fa-solid fa-check text-emerald"></i> ${p}</li>`).join('');
        } else {
            reviewProsList.innerHTML = `<li><i class="fa-solid fa-check text-emerald"></i> Excellent ride comfort and handling</li>`;
        }

        if (edmunds.cons && edmunds.cons.length) {
            reviewConsList.innerHTML = edmunds.cons.map(c => `<li><i class="fa-solid fa-triangle-exclamation text-rose"></i> ${c}</li>`).join('');
        } else {
            reviewConsList.innerHTML = `<li><i class="fa-solid fa-triangle-exclamation text-rose"></i> Regular fleet maintenance recommended</li>`;
        }

        reviewVerdictText.textContent = edmunds.verdict || 'A solid vehicle offering outstanding overall utility and performance.';
        reviewEdmundsLink.href = edmunds.url || 'https://www.edmunds.com/';

        // KBB Valuation Population
        const kbb = v.kbbValuation || {};
        const savingsText = kbb.formattedSavings || `$${(kbb.savingsVsKbb || 0).toLocaleString()}`;
        kbbSavingsPill.innerHTML = `<i class="fa-solid fa-piggy-bank"></i> Save ${savingsText} vs KBB Value`;

        kbbSurplusPrice.textContent = `$${v.salesPrice.toLocaleString()}`;
        kbbFairPrice.textContent = kbb.formattedFairPrice || `$${(kbb.fairPurchasePrice || 0).toLocaleString()}`;
        
        kbbRangeMin.textContent = `$${(kbb.privatePartyValue || Math.round((kbb.fairPurchasePrice || 10000)*0.92)).toLocaleString()}`;
        kbbRangeMax.textContent = `$${(kbb.suggestedRetail || Math.round((kbb.fairPurchasePrice || 10000)*1.1)).toLocaleString()}`;
        
        if (kbbRangeBarFill) {
            kbbRangeBarFill.style.width = `${Math.min(100, Math.max(25, 100 - (kbb.savingsPct || 30)))}%`;
        }

        kbbPriceRange.textContent = kbb.priceRange || '$8,000 - $12,000';
        kbbRetailVal.textContent = `$${(kbb.suggestedRetail || Math.round((kbb.fairPurchasePrice || 10000)*1.1)).toLocaleString()}`;
        
        const pctStr = kbb.savingsPct ? ` (${kbb.savingsPct}% off)` : '';
        kbbTotalSavings.textContent = `${savingsText} below KBB Fair Value${pctStr}`;
        kbbOfficialLink.href = kbb.url || 'https://www.kbb.com/';

        reviewModal.classList.add('active');
    };

    // Modal logic
    window.openVinModal = function(vin) {
        const v = allVehicles.find(x => x.vin === vin);
        if (!v) return;

        currentSelectedVin = v.vin;
        reviewModal.classList.remove('active');

        modalTitle.textContent = v.description;
        modalAssetNum.textContent = `Asset #${v.assetNumber}`;
        modalVinDisplay.textContent = `VIN: ${v.vin}`;
        modalPrice.textContent = `$${v.salesPrice.toLocaleString()}`;
        modalVehicleImg.src = v.image;
        modalVehicleImg.style.cursor = 'pointer';
        modalVehicleImg.title = 'Click picture for full details';
        modalVehicleImg.onclick = () => openReviewModal(currentSelectedVin);

        const cyl = v.specs.EngineCylinders ? `V${v.specs.EngineCylinders}` : '';
        const disp = v.specs.DisplacementL ? `${v.specs.DisplacementL}L` : '';
        const hp = v.specs.EngineHP ? ` (${v.specs.EngineHP} HP)` : '';
        const isTurbo = (v.specs.Aspiration || '').toLowerCase().includes('turbo');
        const turboTag = isTurbo ? ' (Turbocharged)' : '';
        modalEngine.textContent = `${disp} ${cyl}${hp}${turboTag}`.trim() || 'Standard Engine';

        const mpgObj = v.mpg || { city: 16, hwy: 22, combined: 18 };
        modalMpg.textContent = `${mpgObj.combined} MPG Comb (${mpgObj.city} City / ${mpgObj.hwy} Hwy)`;

        modalMileage.textContent = `${v.mileage.toLocaleString()} miles`;
        modalDrivetrain.textContent = formatDriveType(v.specs, v.description);
        
        const plantCity = v.specs.PlantCity || '';
        const plantState = v.specs.PlantState || '';
        const plantCountry = v.specs.PlantCountry || '';
        modalPlant.textContent = [plantCity, plantState, plantCountry].filter(Boolean).join(', ') || 'USA Assembly';

        // Render Open Safety Recalls Section
        const recallsData = v.recalls || { count: 0, items: [] };
        const recallCount = recallsData.count || 0;
        
        if (recallCount > 0) {
            recallsHeaderText.innerHTML = `NHTSA Safety Recalls Identified (${recallCount})`;
            recallCountBadge.className = 'recall-count-badge';
            recallCountBadge.textContent = `${recallCount} Safety Recall(s)`;

            recallsList.innerHTML = recallsData.items.map(r => `
                <div class="recall-card">
                    <div class="recall-card-header">
                        <div>
                            <span class="recall-campaign-tag">NHTSA #${r.campaignNumber || 'N/A'}</span>
                            <div class="recall-component-title">${r.component || 'Safety Component'}</div>
                        </div>
                        <span class="recall-date">${r.date || ''}</span>
                    </div>
                    <p class="recall-summary">${r.summary || 'No summary provided.'}</p>
                    ${r.consequence ? `<div class="recall-consequence"><i class="fa-solid fa-triangle-exclamation"></i> <strong>Consequence:</strong> ${r.consequence}</div>` : ''}
                    ${r.remedy ? `<div class="recall-remedy"><i class="fa-solid fa-wrench"></i> <strong>Remedy:</strong> ${r.remedy}</div>` : ''}
                </div>
            `).join('');
        } else {
            recallsHeaderText.innerHTML = `NHTSA Safety Recalls Identified`;
            recallCountBadge.className = 'recall-count-badge clean';
            recallCountBadge.textContent = `0 Open Recalls`;
            recallsList.innerHTML = `
                <div style="text-align: center; padding: 1rem; color: var(--accent-emerald);">
                    <i class="fa-solid fa-circle-check" style="font-size: 1.5rem; margin-bottom: 0.3rem;"></i>
                    <p style="font-size: 0.875rem;">No active safety recall campaigns reported by NHTSA for this vehicle.</p>
                </div>
            `;
        }

        // Render NHTSA Details Table
        const nhtsaKeys = [
            ['Make', v.specs.Make],
            ['Model', v.specs.Model],
            ['Model Year', v.specs.ModelYear],
            ['Engine Aspiration', isTurbo ? 'Turbocharged' : 'Standard'],
            ['EPA Fuel Rating', `${mpgObj.combined} MPG Comb. (${mpgObj.city} City / ${mpgObj.hwy} Hwy)`],
            ['Safety Recalls', `${recallCount} Campaign(s)`],
            ['Trim / Series', [v.specs.Trim, v.specs.Series].filter(Boolean).join(' ') || 'Standard'],
            ['Body Class', v.specs.BodyClass],
            ['Fuel Type', v.specs.FuelTypePrimary],
            ['Vehicle Type', v.specs.VehicleType],
            ['Manufacturer', v.specs.Manufacturer]
        ];

        nhtsaTable.innerHTML = nhtsaKeys.map(([k, val]) => `
            <div class="nhtsa-item">
                <span class="nhtsa-key">${k}</span>
                <span class="nhtsa-val">${val || 'N/A'}</span>
            </div>
        `).join('');

        // Populate Specs Review Preview
        const edmunds = v.edmundsReview || {};
        const kbb = v.kbbValuation || {};

        if (specsEdmundsRating) specsEdmundsRating.textContent = `${edmunds.rating || 4.5} / 5 Rating`;
        if (specsEdmundsSummary) specsEdmundsSummary.textContent = edmunds.summary || 'Consistently rated highly for comfort and performance.';
        if (specsKbbFair) specsKbbFair.textContent = `${kbb.formattedFairPrice || '$12,000'} Fair Value`;
        if (specsKbbSavings) specsKbbSavings.textContent = `Save ${kbb.formattedSavings || '$3,000'} below KBB estimated value`;

        vinModal.classList.add('active');
    };

    // Close Review Modal Handlers
    reviewModalCloseBtn.addEventListener('click', () => {
        reviewModal.classList.remove('active');
    });

    reviewCloseFooterBtn.addEventListener('click', () => {
        reviewModal.classList.remove('active');
    });

    reviewModal.addEventListener('click', (e) => {
        if (e.target === reviewModal) {
            reviewModal.classList.remove('active');
        }
    });

    reviewSwitchToSpecsBtn.addEventListener('click', () => {
        if (currentSelectedVin) {
            openVinModal(currentSelectedVin);
        }
    });

    if (viewFullReviewBtn) {
        viewFullReviewBtn.addEventListener('click', () => {
            if (currentSelectedVin) {
                openReviewModal(currentSelectedVin);
            }
        });
    }

    modalCloseBtn.addEventListener('click', () => {
        vinModal.classList.remove('active');
    });

    vinModal.addEventListener('click', (e) => {
        if (e.target === vinModal) {
            vinModal.classList.remove('active');
        }
    });

    copyVinBtn.addEventListener('click', () => {
        if (!currentSelectedVin) return;
        navigator.clipboard.writeText(currentSelectedVin).then(() => {
            const originalHTML = copyVinBtn.innerHTML;
            copyVinBtn.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
            setTimeout(() => {
                copyVinBtn.innerHTML = originalHTML;
            }, 2000);
        });
    });

    // Refresh Data handler
    refreshDataBtn.addEventListener('click', () => {
        refreshDataBtn.disabled = true;
        refreshDataBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Syncing Live...`;
        
        fetch('/api/refresh', { method: 'POST' })
            .then(res => res.json())
            .then(resData => {
                if (resData.status === 'success') {
                    return fetch('data/vehicles_final.json?t=' + Date.now())
                        .catch(() => fetch('vehicles_final.json?t=' + Date.now()))
                        .then(r => r.json())
                        .then(data => {
                            if (Array.isArray(data)) {
                                allVehicles = data;
                                updateTimestampUI(null);
                            } else {
                                allVehicles = data.vehicles || [];
                                updateTimestampUI(data.generatedAt);
                            }
                            updateStats(allVehicles);
                            renderVehicles();

                            
                            refreshDataBtn.disabled = false;
                            refreshDataBtn.innerHTML = `<i class="fa-solid fa-check"></i> Synced Live!`;
                            setTimeout(() => {
                                refreshDataBtn.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Sync Live Inventory`;
                            }, 3000);
                        });
                } else {
                    throw new Error(resData.message);
                }
            })
            .catch(err => {
                console.warn('Live API server sync unavailable (static host / GitHub Pages mode):', err);
                refreshDataBtn.disabled = false;
                refreshDataBtn.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Sync Live Inventory`;
                
                // Show friendly GitHub Pages notification instead of harsh alert
                const isGithubPages = window.location.hostname.includes('github.io') || window.location.protocol === 'file:';
                if (isGithubPages) {
                    alert('📌 GitHub Pages Hosted Mode:\nLive inventory data is automatically synced every 6 hours via GitHub Actions!\n\nTo run manual on-demand sync, start server.py locally.');
                } else {
                    alert('Live sync request failed: ' + err.message + '\nEnsure local server.py is running on port 8080.');
                }
            });
    });

    // About Modal Handlers
    const aboutAppBtn = document.getElementById('about-app-btn');
    const aboutModal = document.getElementById('about-modal');
    const aboutModalCloseBtn = document.getElementById('about-modal-close-btn');
    const aboutModalCloseFooterBtn = document.getElementById('about-modal-close-footer-btn');

    if (aboutAppBtn && aboutModal) {
        aboutAppBtn.addEventListener('click', () => {
            aboutModal.classList.add('active');
        });
        if (aboutModalCloseBtn) {
            aboutModalCloseBtn.addEventListener('click', () => {
                aboutModal.classList.remove('active');
            });
        }
        if (aboutModalCloseFooterBtn) {
            aboutModalCloseFooterBtn.addEventListener('click', () => {
                aboutModal.classList.remove('active');
            });
        }
        aboutModal.addEventListener('click', (e) => {
            if (e.target === aboutModal) {
                aboutModal.classList.remove('active');
            }
        });
    }

    // Filter event listeners
    searchInput.addEventListener('input', renderVehicles);
    makeFilter.addEventListener('change', renderVehicles);
    bodyFilter.addEventListener('change', renderVehicles);
    sortSelect.addEventListener('change', renderVehicles);
});

