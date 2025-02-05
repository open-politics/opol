from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from core.models import Content
from core.adb import get_session
import asyncio
from core.utils import logger
from opol.main import OPOL
from opol.api.embeddings import Embeddings
import numpy as np
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import random
import json
import os
import itertools
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from opol.api.classification import Classification

api_key = os.getenv("GOOGLE_API_KEY")
fastclass = Classification(mode="local", provider="Google", model_name="models/gemini-1.5-flash-latest", llm_api_key=api_key)

class Cluster(BaseModel):
    """
    This is a cluster, you should find out if this is a coherent cluster and try to give it a name.
    """
    description_name: str
    description_text: str
    coherent: bool
    coherence_score: int = Field(description="A score between 0 and 10")

class PlotTitles:
    def __init__(self, mode="local", use_preset=True, fixed_seed=40, cache_embeddings=True):
        self.opol = OPOL(mode=mode)
        self.PULL_FRESH_TITLES = True
        self.SAVE_DATA = True
        self.USE_PRESET = True
        self.CACHE_EMBEDDINGS = cache_embeddings
        self.EMBEDDINGS_CACHE_PATH = '/app/data/embeddings.json'
        self.HYPERPARAMS = {
            "pca_n_components": [50, 100],
            "tsne_perplexity": [5, 30],
            "tsne_learning_rate": [200, 500],
            "kmeans_n_clusters": [10, 15]
        }
        if self.USE_PRESET:
            self.HYPERPARAMS = {
                "pca_n_components": [100],
                "tsne_perplexity": [10],

                "tsne_learning_rate": [500],
                "kmeans_n_clusters": list(range(10, 40))
            }
        self.param_combinations = list(itertools.product(
            self.HYPERPARAMS["pca_n_components"],
            self.HYPERPARAMS["tsne_perplexity"],
            self.HYPERPARAMS["tsne_learning_rate"],
            self.HYPERPARAMS["kmeans_n_clusters"]
        ))
        self.fixed_seed = fixed_seed
        self.setup_environment()

    def setup_environment(self):
        os.makedirs('/app/data/', exist_ok=True)
        os.makedirs('/app/results/', exist_ok=True)
        self.embedder = Embeddings(
            mode="local",
            use_api=True,
            api_provider="jina",
            api_provider_key="jina_fe65f3ce923144cfa62344d5bac6255cGktxpN8hXB_VwOUzISw3JRXPwPE2"
        )
        self.set_seed(self.fixed_seed)

    def set_seed(self, seed):
        random.seed(seed)
        np.random.seed(seed)

    async def get_contents(self):
        if not self.PULL_FRESH_TITLES:
            try:
                with open('/app/data/titles.json', 'r') as f:
                    cached_data = json.load(f)
                    contents = cached_data.get("contents", [])
                    return {"contents": contents}
            except FileNotFoundError:
                logger.warning("Cached data not found. Fetching fresh titles.")
        
        try:
            async_session = get_session()
            async for session in async_session:
                query = select(Content).where(Content.insertion_date > datetime.now() - timedelta(days=2)).order_by(Content.insertion_date.desc()).limit(400)
                result = await session.execute(query)
                contents = result.scalars().all()
                if self.SAVE_DATA:
                    serialized_contents = [{"title": content.title} for content in contents]
                    with open('/app/data/titles.json', 'w') as f:
                        json.dump({"contents": serialized_contents}, f)
                return {"contents": contents}
        except Exception as e:
            logger.error(f"Error plotting contents: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error plotting contents")

    async def load_cached_embeddings(self):
        try:
            with open(self.EMBEDDINGS_CACHE_PATH, 'r') as f:
                cache = json.load(f)
                titles = cache.get("titles", [])
                embeddings = cache.get("embeddings", [])
                return titles, embeddings
        except FileNotFoundError:
            logger.warning("Embeddings cache not found.")
            return None, None
        except Exception as e:
            logger.error(f"Error loading embeddings cache: {e}", exc_info=True)
            return None, None

    async def save_embeddings_to_cache(self, titles, embeddings):
        try:
            with open(self.EMBEDDINGS_CACHE_PATH, 'w') as f:
                json.dump({"titles": titles, "embeddings": embeddings}, f)
            logger.info("Embeddings cached successfully.")
        except Exception as e:
            logger.error(f"Error saving embeddings to cache: {e}", exc_info=True)

    async def generate_embedding(self, title):
        return await asyncio.to_thread(self.embedder.generate, title, "separation")

    async def generate_llm_labels(self, clusters, list_of_titles):
        llm_labeled_clusters = []
        for cluster_id, titles in clusters.items():
            cluster_names = titles[:3]  # Taking first 3 titles as examples
            cluster_name = fastclass.classify(Cluster, "", cluster_names)
            llm_labeled_clusters.append(cluster_name)
        return llm_labeled_clusters

    async def dev(self):
        if self.CACHE_EMBEDDINGS:
            cached_titles, cached_embeddings = await self.load_cached_embeddings()
            if cached_titles and cached_embeddings:
                logger.info("Loaded embeddings from cache.")
                list_of_titles = cached_titles
                list_of_embeddings = cached_embeddings
                list_of_tags = ["News", "Sports", "Politics", "Entertainment", "Technology", "Science", "Health", "Business", "Education", "Environment", "Culture", "Travel", "Food", "Fashion", "Art", "Music", "Movies", "TV", "Gaming", "Animals"]
                # Assuming cached_clusters are stored or can be generated
                # Here we will generate dummy labels; replace with actual logic if available
                llm_labeled_clusters = [
                    Cluster(description_name="Trump's Inauguration and Early Presidency", 
                            description_text="This cluster contains news articles and features related to Donald Trump's inauguration and the early actions taken during his presidency, including executive orders, political reactions, and fashion choices.", 
                            coherent=True, coherence_score=9),
                    Cluster(description_name='Diverse News Events', 
                            description_text='This cluster contains news stories covering a wide range of topics, including weather events, political news, technological advancements, and human interest stories. The lack of a central theme makes it less coherent.', 
                            coherent=False, coherence_score=3),
                    # Add more Cluster instances as needed
                ]
                return list_of_titles, list_of_embeddings, list_of_tags, llm_labeled_clusters

        list_of_titles = []
        list_of_embeddings = []
        contents = await self.get_contents()
        tasks = []
        
        for content in contents["contents"]:
            list_of_titles.append(content.title)
            tasks.append(self.generate_embedding(content.title))
        
        list_of_embeddings = await asyncio.gather(*tasks)
        
        if self.CACHE_EMBEDDINGS:
            await self.save_embeddings_to_cache(list_of_titles, list_of_embeddings)

        list_of_tags = ["News", "Sports", "Politics", "Entertainment", "Technology", "Science", "Health", "Business", "Education", "Environment", "Culture", "Travel", "Food", "Fashion", "Art", "Music", "Movies", "TV", "Gaming", "Animals"]
        # Generate cluster labels
        # This should ideally be done after clustering, so placeholder here
        llm_labeled_clusters = []  # Replace with actual label generation logic
        return list_of_titles, list_of_embeddings, list_of_tags, llm_labeled_clusters

    def find_optimal_clusters(self, embeddings, max_clusters=20):
        silhouette_scores = {}
        for n_clusters in range(2, max_clusters + 1):
            kmeans = KMeans(n_clusters=n_clusters, random_state=self.fixed_seed)
            cluster_labels = kmeans.fit_predict(embeddings)
            score = silhouette_score(embeddings, cluster_labels)
            silhouette_scores[n_clusters] = score
            logger.info(f"Silhouette Score for {n_clusters} clusters: {score}")

        optimal_clusters = max(silhouette_scores, key=silhouette_scores.get)
        logger.info(f"Optimal number of clusters determined: {optimal_clusters}")
        return optimal_clusters

    def compute_cluster_centers(self, embeddings, cluster_labels):
        """
        Compute the centroid of each cluster by averaging its members' embeddings.
        """
        unique_clusters = np.unique(cluster_labels)
        centers = []
        for clu in unique_clusters:
            indices = np.where(cluster_labels == clu)[0]
            cluster_embs = embeddings[indices]
            center = np.mean(cluster_embs, axis=0)
            centers.append(center)
        return np.array(centers)

    def merge_similar_clusters(self, embeddings, cluster_labels, threshold=0.8):
        """
        Merge clusters that are too similar based on their cosine similarity.
        threshold = 0.8 means that any two clusters with >= 0.8 similarity get merged.
        Returns new cluster labels.
        """
        from numpy.linalg import norm

        # Compute all cluster centers
        centers = self.compute_cluster_centers(embeddings, cluster_labels)

        # Compute pairwise similarities
        n = len(centers)
        to_merge = {}
        merged = set()

        for i in range(n):
            for j in range(i + 1, n):
                if i in merged or j in merged:
                    continue
                dot_product = np.dot(centers[i], centers[j])
                sim = dot_product / (norm(centers[i]) * norm(centers[j]) + 1e-9)
                if sim >= threshold:
                    # Mark clusters j to be merged into i
                    to_merge[j] = i
                    merged.add(j)

        # Generate new labels
        new_labels = cluster_labels.copy()
        for old_clu, new_clu in to_merge.items():
            new_labels[cluster_labels == old_clu] = new_clu

        # Optional: re-label clusters from 0...n_merged-1 for clarity
        unique_old = np.unique(new_labels)
        remap = {old: idx for idx, old in enumerate(unique_old)}
        final_labels = np.array([remap[x] for x in new_labels], dtype=int)

        return final_labels

    def prune_outliers(self, embeddings, cluster_labels, max_dist=0.5):
        """
        Remove items that are too far from their cluster centroid.
        If the distance is more than max_dist, we can label them as -1 (or discard).
        """
        from numpy.linalg import norm

        centers = self.compute_cluster_centers(embeddings, cluster_labels)
        new_labels = cluster_labels.copy()

        for i in range(len(new_labels)):
            clu = cluster_labels[i]
            center = centers[clu]
            dist = 1.0 - (np.dot(embeddings[i], center) / (norm(embeddings[i]) * norm(center) + 1e-9))
            if dist > max_dist:
                # Label as outlier or remove
                new_labels[i] = -1  # -1 could indicate "thrown away"

        return new_labels

    async def plot_embeddings(self, list_of_titles, list_of_embeddings, pca_n, tsne_p, tsne_lr, kmeans_k, llm_labeled_clusters):
        # Normalize embeddings
        list_of_embeddings = list_of_embeddings / np.linalg.norm(list_of_embeddings, axis=1, keepdims=True)

        # Perform PCA
        pca = PCA(n_components=pca_n, random_state=self.fixed_seed)
        reduced_embeddings = pca.fit_transform(list_of_embeddings)

        # Perform KMeans clustering
        kmeans = KMeans(n_clusters=kmeans_k, random_state=self.fixed_seed)
        clusters = kmeans.fit_predict(reduced_embeddings)

        # --------------------------------------------------------------------------------
        # OPTIONAL STEP 1: Merge clusters that are too close
        clusters = self.merge_similar_clusters(reduced_embeddings, clusters, threshold=0.8)

        # OPTIONAL STEP 2: Prune outliers that are too far from cluster centers
        clusters = self.prune_outliers(reduced_embeddings, clusters, max_dist=0.5)
        # --------------------------------------------------------------------------------

        # Build cluster_titles again after merges
        unique_clusters = np.unique(clusters[clusters != -1])
        cluster_titles = {clu: [] for clu in unique_clusters}
        for title, cluster_id in zip(list_of_titles, clusters):
            if cluster_id >= 0:
                cluster_titles[cluster_id].append(title)

        # Generate LLM labels for clusters (fastclass can help refine merges/rankings)
        llm_labeled_clusters = await self.generate_llm_labels(cluster_titles, list_of_titles)

        for llm_labeled_cluster in llm_labeled_clusters:
            print("*" * 100)
            print(llm_labeled_cluster)
            print("*" * 100)

        # Perform t-SNE
        tsne = TSNE(n_components=2, random_state=self.fixed_seed, perplexity=tsne_p, learning_rate=tsne_lr)
        embeddings_2d = tsne.fit_transform(reduced_embeddings)

        # Plotting
        plt.figure(figsize=(12, 10))
        scatter = plt.scatter(embeddings_2d[:, 0], embeddings_2d[:, 1],
                              c=clusters, cmap='tab20', label='Embeddings')

        # Use PCA for centers
        centers = kmeans.cluster_centers_
        centers_2d = PCA(n_components=2, random_state=self.fixed_seed).fit_transform(centers)
        plt.scatter(centers_2d[:, 0], centers_2d[:, 1], c='red', s=100, alpha=0.75, label='Centers')

        for i, center in enumerate(centers_2d):
            if i < len(llm_labeled_clusters):
                cluster_label = llm_labeled_clusters[i].description_name
            else:
                cluster_label = f'Cluster {i}'
            plt.text(center[0], center[1], f'{cluster_label}', fontsize=9, ha='right')

        # Annotate random samples from each cluster
        for cluster_id in range(kmeans_k):
            cluster_indices = np.where(clusters == cluster_id)[0]
            if len(cluster_indices) > 0:
                for _ in range(min(2, len(cluster_indices))):
                    random_index = random.choice(cluster_indices)
                    x, y = embeddings_2d[random_index]
                    plt.text(x, y, list_of_titles[random_index], fontsize=8, ha='right', color='black')

        plt.grid(True)
        plt.title(f'2D Embeddings Visualization\nPCA={pca_n}, t-SNE Perp={tsne_p}, t-SNE LR={tsne_lr}, KMeans Clusters={kmeans_k}')
        plt.xlabel('Dimension 1')
        plt.ylabel('Dimension 2')
        plt.legend()

        # Save plot with hyperparameters in the filename
        unique_hash = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
        plot_filename = f"/app/results/embeddings_pca{pca_n}_tsneP{tsne_p}_tsneLR{tsne_lr}_k{kmeans_k}_hash{unique_hash}.png"
        plt.savefig(plot_filename)
        plt.close()
        logger.info(f"Saved plot to {plot_filename}")

    async def tune_hyperparameters(self):
        list_of_titles, list_of_embeddings, list_of_tags, llm_labeled_clusters = await self.dev()
        list_of_embeddings = np.array(list_of_embeddings)

        # Determine the optimal number of clusters
        optimal_k = self.find_optimal_clusters(list_of_embeddings)

        # Update hyperparameters with the optimal number of clusters
        self.HYPERPARAMS["kmeans_n_clusters"] = [optimal_k]
        self.param_combinations = list(itertools.product(
            self.HYPERPARAMS["pca_n_components"],
            self.HYPERPARAMS["tsne_perplexity"],
            self.HYPERPARAMS["tsne_learning_rate"],
            self.HYPERPARAMS["kmeans_n_clusters"]
        ))

        for idx, (pca_n, tsne_p, tsne_lr, kmeans_k) in enumerate(self.param_combinations):
            logger.info(f"Processing combination {idx + 1}/{len(self.param_combinations)}: PCA={pca_n}, t-SNE Perplexity={tsne_p}, t-SNE Learning Rate={tsne_lr}, KMeans Clusters={kmeans_k}")
            try:
                await self.plot_embeddings(list_of_titles, list_of_embeddings, pca_n, tsne_p, tsne_lr, kmeans_k, llm_labeled_clusters)
            except Exception as e:
                logger.error(f"Error processing combination {idx + 1}: {e}", exc_info=True)

        logger.info("Hyperparameter tuning completed.")

    def run(self):
        asyncio.run(self.tune_hyperparameters())

if __name__ == "__main__":
    plot_titles = PlotTitles()
    plot_titles.run()