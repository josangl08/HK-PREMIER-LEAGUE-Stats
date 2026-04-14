// Mutate the existing dash_clientside object in place — never replace it with a new reference.
// Object.assign({}, ...) creates a new object and breaks any cached dc reference inside dash_renderer.
window.dash_clientside = window.dash_clientside || {};
window.dash_clientside.playerPortal = {
    scrollYearNavigator: function(children, selected_year) {
        if (!children || children.length === 0) return null;
        var targetYear = selected_year ? selected_year.toString() : new Date().getFullYear().toString();
        requestAnimationFrame(function() {
            var bar = document.getElementById("year-navigator-pills");
            if (!bar) return;
            var buttons = bar.querySelectorAll("button");
            for (var i = 0; i < buttons.length; i++) {
                if (buttons[i].textContent.trim() === targetYear) {
                    buttons[i].scrollIntoView({behavior: "auto", inline: "center", block: "nearest"});
                    break;
                }
            }
        });
        return null;
    },

    scrollTimelineToYear: function(selected_year) {
        if (!selected_year) return null;
        requestAnimationFrame(function() {
            var container = document.querySelector(".milestone-list-container");
            if (!container) return;
            var target = container.querySelector(".year-" + selected_year);
            if (target) {
                target.scrollIntoView({behavior: "auto", block: "start"});
            }
        });
        return null;
    },

    loadMoreMilestones: function(n_clicks_list) {
        var triggered = dash_clientside.callback_context.triggered_id;
        if (!triggered || triggered.type !== "load-more-btn") {
            return window.dash_clientside.no_update;
        }
        if (!n_clicks_list || !n_clicks_list.some(function(v) { return v > 0; })) {
            return window.dash_clientside.no_update;
        }

        var year = triggered.year;
        var season = document.querySelector('.season-section[data-year="' + year + '"]');
        if (!season) return window.dash_clientside.no_update;

        var hiddenItems = season.querySelectorAll(".timeline-item-hidden");
        var shown = 0;
        for (var i = 0; i < hiddenItems.length && shown < 10; i++) {
            hiddenItems[i].style.removeProperty("display");
            hiddenItems[i].classList.remove("timeline-item-hidden");
            shown++;
        }

        var remaining = season.querySelectorAll(".timeline-item-hidden");
        if (remaining.length === 0) {
            var row = season.querySelector(".load-more-row");
            if (row) row.style.display = "none";
        }
        return window.dash_clientside.no_update;
    },

    toggleTimelineExpand: function(n_clicks_list, expand_store) {
        var triggered_id = dash_clientside.callback_context.triggered_id;
        if (!triggered_id || triggered_id.type !== "milestone-header") {
            return window.dash_clientside.no_update;
        }
        var triggered = dash_clientside.callback_context.triggered;
        var triggerValue = (triggered && triggered[0] && triggered[0].value) || 0;
        if (!triggerValue) {
            return window.dash_clientside.no_update;
        }

        var mid = triggered_id.index;
        var open_ids = new Set(expand_store || []);
        var selector = '[id*="index"][id*="' + mid + '"][id*="type"][id*="milestone-header"]';
        var headerEl = document.querySelector(selector);
        if (!headerEl) return window.dash_clientside.no_update;

        var eventContainer = headerEl.closest(".timeline-event");
        if (!eventContainer) return window.dash_clientside.no_update;

        var seasonContainer = eventContainer.closest(".season-group-container");
        var isCareerHeader = seasonContainer && seasonContainer.getAttribute("data-career-id") === mid;
        var willOpen = !open_ids.has(mid);

        if (isCareerHeader) {
            if (willOpen) {
                document.querySelectorAll(".season-group-container").forEach(function(el) {
                    var cid = el.getAttribute("data-career-id");
                    if (!cid) return;
                    open_ids.delete(cid);
                    el.querySelectorAll(".timeline-event").forEach(function(item) {
                        var itemHeader = item.querySelector(".milestone-header");
                        if (!itemHeader || !itemHeader.id) return;
                        try {
                            var parsed = JSON.parse(itemHeader.id);
                            if (parsed && parsed.index) open_ids.delete(parsed.index);
                        } catch (e) {}
                    });
                });
                open_ids.add(mid);
            } else {
                open_ids.delete(mid);
                seasonContainer.querySelectorAll(".timeline-event").forEach(function(item) {
                    var itemHeader = item.querySelector(".milestone-header");
                    if (!itemHeader || !itemHeader.id) return;
                    try {
                        var parsed = JSON.parse(itemHeader.id);
                        if (parsed && parsed.index) open_ids.delete(parsed.index);
                    } catch (e) {}
                });
            }
        } else {
            var parentCareerId = seasonContainer ? seasonContainer.getAttribute("data-career-id") : null;
            if (willOpen) {
                if (seasonContainer) {
                    var matchesGroup = seasonContainer.querySelector(".season-matches-group");
                    if (matchesGroup) {
                        matchesGroup.querySelectorAll(".timeline-event").forEach(function(item) {
                            if (item === eventContainer) return;
                            var itemHeader = item.querySelector(".milestone-header");
                            if (!itemHeader || !itemHeader.id) return;
                            try {
                                var parsed = JSON.parse(itemHeader.id);
                                if (parsed && parsed.index) open_ids.delete(parsed.index);
                            } catch (e) {}
                        });
                    }
                    if (parentCareerId) open_ids.add(parentCareerId);
                }
                open_ids.add(mid);
            } else {
                open_ids.delete(mid);
                if (parentCareerId) open_ids.add(parentCareerId);
            }
        }
        return Array.from(open_ids);
    },

    syncTimelineExpandedClasses: function(expand_store, children) {
        if (!children) return window.dash_clientside.no_update;
        var openIds = new Set(expand_store || []);
        requestAnimationFrame(function() {
            document.querySelectorAll(".timeline-event").forEach(function(el) {
                el.classList.remove("is-expanded");
            });
            document.querySelectorAll(".season-group-container").forEach(function(el) {
                el.classList.remove("is-expanded");
            });

            openIds.forEach(function(mid) {
                var selector = '[id*="index"][id*="' + mid + '"][id*="type"][id*="milestone-header"]';
                var headerEl = document.querySelector(selector);
                if (!headerEl) return;
                var eventContainer = headerEl.closest(".timeline-event");
                if (eventContainer) eventContainer.classList.add("is-expanded");
                var seasonContainer = headerEl.closest(".season-group-container");
                if (seasonContainer) seasonContainer.classList.add("is-expanded");
            });
        });
        return null;
    },

    observeSeasonSections: function(children) {
        requestAnimationFrame(function() {
            if (window.lucide) window.lucide.createIcons();
        });

        setTimeout(function() {
            if (window._seasonObserver) {
                window._seasonObserver.disconnect();
            }
            var container = document.querySelector(".milestone-list-container");
            var sections = document.querySelectorAll(".season-section");
            if (!sections || !sections.length) return;
            window._portalActiveSeasonYear = null;

            window._seasonObserver = new IntersectionObserver(function(entries) {
                var topYear = null;
                var topPos = Infinity;
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        var top = Math.abs(entry.boundingClientRect.top);
                        if (top < topPos) {
                            topPos = top;
                            topYear = entry.target.getAttribute("data-year");
                        }
                    }
                });
                if (!topYear) return;
                if (window._portalActiveSeasonYear === topYear) return;
                window._portalActiveSeasonYear = topYear;

                var pills = document.querySelectorAll("#year-navigator-pills button");
                pills.forEach(function(pill) {
                    var pillYear = pill.textContent.trim();
                    if (pillYear === topYear) {
                        pill.classList.add("active");
                    } else {
                        pill.classList.remove("active");
                    }
                });
            }, {threshold: 0.2, root: container});

            sections.forEach(function(section) {
                window._seasonObserver.observe(section);
            });
        }, 120);
        return null;
    },

    refreshStageLucide: function(children) {
        requestAnimationFrame(function() {
            if (window.lucide) window.lucide.createIcons();
        });
        return null;
    },

    scrollPrematchH2H: function(n_clicks) {
        if (!n_clicks) return window.dash_clientside.no_update;
        var scroller = document.querySelector(".prematch-h2h-scroll");
        if (!scroller) return window.dash_clientside.no_update;
        var nextItem = scroller.querySelector(".prematch-h2h-item--future");
        var nowItem = scroller.querySelector(".prematch-h2h-item--now");
        var target = nextItem || nowItem;
        if (!target) return window.dash_clientside.no_update;

        var targetLeft = target.offsetLeft;
        var targetWidth = target.offsetWidth;
        var desired = Math.max(0, Math.min(
            scroller.scrollWidth - scroller.clientWidth,
            targetLeft + targetWidth - scroller.clientWidth + 22
        ));
        scroller.scrollTo({left: desired, behavior: "auto"});
        return n_clicks;
    },

    togglePortalViewport: function(detail_clicks, action_pill_clicks, back_clicks) {
        var triggered = dash_clientside.callback_context.triggered;
        if (!triggered || triggered.length === 0) {
            return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        }
        var prop_id = triggered[0].prop_id || "";
        if (prop_id.includes("milestone-detail-btn") || prop_id.includes("action-node-pill")) {
            return ["portal-viewport show-stage", {panel: "stage"}];
        }
        if (prop_id === "portal-back-btn.n_clicks") {
            return ["portal-viewport", {panel: "timeline"}];
        }
        return [window.dash_clientside.no_update, window.dash_clientside.no_update];
    },

    toggleCardDetailPanels: function(n_clicks_list, card_expand_store) {
        var triggered_id = dash_clientside.callback_context.triggered_id;
        if (!triggered_id || triggered_id.type !== "card-header") {
            return [window.dash_clientside.no_update, window.dash_clientside.no_update];
        }
        var mid = triggered_id.index;
        var store = card_expand_store || {};
        var isOpen = !!store[mid];
        var newStore = {};
        if (!isOpen) newStore[mid] = true;

        var header_inputs = dash_clientside.callback_context.inputs_list[0];
        var styles = header_inputs.map(function(inp) {
            return newStore[inp.id.index] ? {display: "block"} : {display: "none"};
        });
        return [newStore, styles];
    },

    observeCareerArc: function(stage_content) {
        if (!stage_content) return window.dash_clientside.no_update;
        setTimeout(function() {
            var careerArc = document.querySelector(".career-arc-section, [id*=\"career-arc\"]");
            if (!careerArc) return;
            if (careerArc._t2ObserverRegistered) return;
            careerArc._t2ObserverRegistered = true;

            var observer = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.intersectionRatio >= 0.5) {
                        var store = document.getElementById("t2-overlay-queue");
                        if (store && !store._careerTrajectoryQueued) {
                            store._careerTrajectoryQueued = true;
                            var event = new CustomEvent("career-arc-visible");
                            document.dispatchEvent(event);
                        }
                    }
                });
            }, {threshold: 0.5});

            observer.observe(careerArc);
        }, 300);
        return window.dash_clientside.no_update;
    }
};
